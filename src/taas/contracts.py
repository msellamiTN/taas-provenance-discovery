"""Capability contracts (Definition 4) and their extraction from MCP tool definitions (Section 6.1).

c(t) = (in(t), out(t), eff(t), flow(t), req(t), qos(t), srv(t), λ_t, h(t)).
Every assertion carries a provenance record; ``props`` holds the property assertions
(read_only, writes, ...) used by the bitmap index, ``eff`` the scoped effect set from the
strongest available evidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable

from .data.registries import RawTool
from .effects import Effect, FlowTransformer, lexical_effects, parse_effects
from .provenance import NEGATION, ProvenanceRecord, TrustPolicy, DEFAULT_TRUST, EvidenceStore
from .types import SemType, TypeAssignment, parse_type, tau_arg, tau_out


@dataclass(frozen=True)
class Arg:
    name: str
    type: SemType
    required: bool
    confidence: float = 1.0
    domain: tuple | None = None


@dataclass(frozen=True)
class QoS:
    price: float = 0.0
    latency: float = 1.0
    fail: float = 0.05
    source: str = "default"


@dataclass
class CapabilityContract:
    tool: str                                   # server::name
    name: str
    server: str
    description: str
    args: tuple[Arg, ...]
    out: TypeAssignment
    eff: frozenset[Effect]
    eff_record: ProvenanceRecord                # provenance of the effect clause
    flow: FlowTransformer
    req: tuple[str, ...]
    qos: QoS
    srv: dict
    props: dict[str, list[ProvenanceRecord]]    # λ_t over property assertions
    h: str
    tool_class: str = "other"
    tokens: int = 0
    annotations: dict | None = None

    @property
    def tail(self) -> tuple[SemType, ...]:
        """T(e): required argument types."""
        return tuple(a.type for a in self.args if a.required)

    @property
    def head(self) -> SemType:
        return self.out.type

    def strength(self, prop: str, trust: TrustPolicy = DEFAULT_TRUST) -> float:
        recs = self.props.get(prop, [])
        return max((trust.strength(prop, r) for r in recs), default=0.0)

    def eff_strength(self, trust: TrustPolicy = DEFAULT_TRUST) -> float:
        return trust.strength("effects", self.eff_record)

    def rendering(self) -> str:
        return f"{self.name.replace('_', ' ').replace('-', ' ')} {self.server} {self.tool_class} {self.description}"


def _effect_props(effects: Iterable[Effect]) -> dict[str, bool]:
    cl = {e.cls for e in effects}
    return {"read_only": not (cl & {"write", "delete", "exec", "money"}),
            "no_delete": "delete" not in cl, "no_exec": "exec" not in cl,
            "no_money": "money" not in cl, "no_egress": "egress" not in cl}


def props_from_effects(effects: Iterable[Effect], rec: ProvenanceRecord) -> dict[str, list[ProvenanceRecord]]:
    """Positive assertions for properties that hold, negative (violation) assertions for those that fail."""
    out: dict[str, list[ProvenanceRecord]] = {}
    neg_of = {v: k for k, v in NEGATION.items()}
    for p, holds in _effect_props(effects).items():
        out.setdefault(p if holds else neg_of[p], []).append(rec)
    return out


def props_from_annotations(ann: dict | None) -> dict[str, list[ProvenanceRecord]]:
    """MCP annotations as ann-evidence. Missing hints assert nothing."""
    if not ann:
        return {}
    rec = ProvenanceRecord("ann", None, 1.0, "mcp-annotation")
    out: dict[str, list[ProvenanceRecord]] = {}
    ro = ann.get("readOnlyHint")
    if ro is True:
        for p in ("read_only", "no_delete", "no_exec", "no_money"):
            out.setdefault(p, []).append(rec)
    elif ro is False:
        out.setdefault("writes", []).append(rec)
        if ann.get("destructiveHint") is True:
            out.setdefault("deletes", []).append(rec)
        elif ann.get("destructiveHint") is False:
            out.setdefault("no_delete", []).append(rec)
    if ann.get("openWorldHint") is False:
        out.setdefault("no_egress", []).append(rec)
    elif ann.get("openWorldHint") is True:
        out.setdefault("egresses", []).append(rec)
    return out


def _merge(*dicts: dict[str, list[ProvenanceRecord]]) -> dict[str, list[ProvenanceRecord]]:
    out: dict[str, list[ProvenanceRecord]] = {}
    for d in dicts:
        for k, v in d.items():
            out.setdefault(k, []).extend(v)
    return out


def extract_contract(t: RawTool, typing: dict | None = None, store: EvidenceStore | None = None,
                     qos: QoS | None = None, source_label: str | None = None) -> CapabilityContract:
    """Contract extraction (Section 6.1).

    ``typing`` is the LLM-assisted τ output for this tool (``in``, ``out``, ``class``) when
    available; otherwise structural+lexical τ is used. ``store`` provides obs/att evidence
    bound to (t, h(t)). Effects come from the strongest evidence: att/obs observed effects,
    else annotations (read-only claim ⇒ {read}), else lexical labelling.
    """
    h = t.definition_hash()
    props_schema = (t.input_schema or {}).get("properties", {}) or {}
    required = set((t.input_schema or {}).get("required", []) or [])
    ty_in = (typing or {}).get("in", {}) or {}
    args = []
    for a, s in props_schema.items():
        if a in ty_in:
            ta = TypeAssignment(parse_type(ty_in[a]), 0.85, "llm")
        else:
            ta = tau_arg(a, s if isinstance(s, dict) else {}, "")
        args.append(Arg(a, ta.type, a in required, ta.confidence))
    if typing and typing.get("out"):
        out = TypeAssignment(parse_type(typing["out"]), 0.85, "llm")
    else:
        out = tau_out(t.name, t.description, t.output_schema)
    tool_class = (typing or {}).get("class", "other") or "other"

    arg_names = list(props_schema)
    lex_eff = lexical_effects(t.name, t.description, arg_names)
    lex_rec = ProvenanceRecord("lex", None, 1.0, "name+verb+args")
    props = props_from_effects(lex_eff, lex_rec)
    props = _merge(props, props_from_annotations(t.annotations))
    eff, eff_rec = lex_eff, lex_rec
    ro = (t.annotations or {}).get("readOnlyHint")
    if ro is True:
        eff, eff_rec = frozenset({Effect("read", "*")} | {e for e in lex_eff if e.cls == "egress"}), \
            ProvenanceRecord("ann", None, 1.0, "mcp-annotation")
    if store is not None:
        stored = store.get(t.id, h)
        props = _merge(props, stored)
        obs_eff = store.effects(t.id, h)
        if obs_eff is not None:
            best = max((r for rs in stored.values() for r in rs), key=lambda r: ("lex", "ann", "obs", "att").index(r.ptype),
                       default=ProvenanceRecord("obs", "sandbox", 1.0))
            eff, eff_rec = parse_effects(obs_eff), best
    if source_label is None:
        source_label = "private" if any(e.cls == "read" and e.scope in ("fs", "db", "memory", "email", "local-fs")
                                        for e in eff) else "public"
    req = tuple(a.name for a in args if a.type.kind == "credential")
    tokens = (len(t.description or "") + len(json.dumps(t.input_schema or {}))) // 4
    return CapabilityContract(
        tool=t.id, name=t.name, server=t.server, description=t.description or "", args=tuple(args), out=out,
        eff=frozenset(eff), eff_record=eff_rec, flow=FlowTransformer(source_label), req=req,
        qos=qos or QoS(), srv={"server": t.server, "source": t.source, "transport": "stdio"},
        props=props, h=h, tool_class=tool_class, tokens=tokens, annotations=t.annotations)


def make_contract(tool: str, in_types: dict[str, str], out: str, eff: Iterable[str], evidence: str = "obs",
                  signer: str | None = "registry-A", kappa: float = 1.0, tool_class: str = "other",
                  description: str = "", source_label: str = "public", qos: QoS | None = None,
                  optional: Iterable[str] = (), req: Iterable[str] = ()) -> CapabilityContract:
    """Hand-written contract (scenario registries of Tables 5 and 6, synthetic benchmarks)."""
    server, name = tool.split("::", 1)
    effs = parse_effects(eff)
    rec = ProvenanceRecord(evidence, signer if evidence == "att" else ("sandbox" if evidence == "obs" else None),
                           kappa, "spec")
    args = tuple(Arg(a, parse_type(ty), a not in set(optional)) for a, ty in in_types.items())
    h = str(abs(hash((tool, tuple(in_types.items()), out, tuple(sorted(map(str, effs)))))))[:16]
    return CapabilityContract(
        tool=tool, name=name, server=server, description=description or name.replace("_", " "), args=args,
        out=TypeAssignment(parse_type(out), 1.0, "spec"), eff=effs, eff_record=rec,
        flow=FlowTransformer(source_label), req=tuple(req), qos=qos or QoS(), srv={"server": server},
        props=props_from_effects(effs, rec), h=h, tool_class=tool_class,
        tokens=max(20, len(description) // 4 + 15 * len(in_types)))
