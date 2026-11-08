"""Sanitised manifest (Section 6.3) and the experience repository R of task patterns.

The toolkit is exposed as a manifest whose names, descriptions and argument defaults are rewritten
from the contract rather than copied from the provider, which removes description-borne injection
and confusable neighbours.

Revision 2: ``sanitise`` alone rebuilds descriptions but keeps provider-controlled tool names and argument keys
(the Revision 1 audit found a name canary in 569/569 tools and an argument-key canary in 517). ``manifest`` now
exposes *aliases* (``tool_001``, ``arg_001``) and keeps the alias -> provider binding server-side under
``server_bindings``; ``model_visible`` returns exactly what the model may see. Residual channel: semantic type
strings (``kind:domain``) come from the typing step and are shown; their domain tokens are restricted to
``[a-z0-9_.-]`` here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .certificate import Certificate
from .contracts import CapabilityContract
from .hypergraph import Hypergraph


def sanitise(c: CapabilityContract) -> dict:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", f"{c.server}__{c.name}")[:64]
    args = {a.name: {"type": "string" if a.type.kind not in ("number", "boolean") else
                     ("number" if a.type.kind == "number" else "boolean"),
                     "description": f"{a.type}"} for a in c.args}
    effs = ", ".join(sorted(map(str, c.eff))) or "none"
    desc = (f"{c.tool_class.replace('_', ' ')}: takes "
            f"{', '.join(str(a.type) for a in c.args if a.required) or 'nothing'} and returns {c.head}. "
            f"Effects: {effs}.")
    return {"name": name, "description": desc,
            "inputSchema": {"type": "object", "properties": args,
                            "required": [a.name for a in c.args if a.required]}}


SAFE_CLASSES = {"classify", "extract", "summarise", "summarize", "translate", "convert_format", "aggregate",
                "compute_exactly", "retrieve", "write", "search", "create_document", "send", "delete", "execute",
                "pay", "other"}


def _type_str(t) -> str:
    """Semantic type as shown to the model; domain tokens restricted to a safe alphabet."""
    return re.sub(r"[^a-z0-9_.:\[\]-]", "_", str(t).lower())[:64]


def alias_entry(c: CapabilityContract, alias: str) -> tuple[dict, dict]:
    """Model-visible entry with no provider-controlled identifier, and its server-side binding."""
    props, amap, req = {}, {}, []
    for j, a in enumerate(c.args):
        key = f"arg_{j + 1:03d}"
        kind = a.type.kind
        props[key] = {"type": "number" if kind == "number" else "boolean" if kind == "boolean" else "string",
                      "description": _type_str(a.type)}
        amap[key] = a.name
        if a.required:
            req.append(key)
    cls = c.tool_class if c.tool_class in SAFE_CLASSES else "other"
    effs = ", ".join(sorted(_type_str(e) for e in c.eff)) or "none"
    desc = (f"{cls.replace('_', ' ')}: takes {', '.join(_type_str(a.type) for a in c.args if a.required) or 'nothing'}"
            f" and returns {_type_str(c.head)}. Effects: {effs}.")
    return ({"name": alias, "description": desc, "inputSchema": {"type": "object", "properties": props,
                                                                    "required": req}},
            {"tool_id": c.tool, "definition_hash": c.h, "argument_map": amap})


def manifest(H: Hypergraph, cert: Certificate, order: list[str] | None = None, aliases: bool = True) -> dict:
    """Manifest of a certified toolkit. With ``aliases`` (default) the model sees only aliases; the binding
    to provider identifiers is kept under ``server_bindings`` and must not be serialised to the model."""
    ids = list(cert.toolkit)
    if not aliases:
        return {"tools": [sanitise(H.contracts[t]) for t in ids], "suggested_order": order or ids,
                "certificate": {k: v for k, v in cert.checks.items()}}
    alias_of = {t: f"tool_{i + 1:03d}" for i, t in enumerate(ids)}
    tools, bindings = [], {}
    for t in ids:
        entry, bind = alias_entry(H.contracts[t], alias_of[t])
        tools.append(entry)
        bindings[alias_of[t]] = bind
    return {"tools": tools, "suggested_order": [alias_of[t] for t in (order or ids) if t in alias_of],
            "certificate": {k: v for k, v in cert.checks.items()}, "server_bindings": bindings}


def model_visible(m: dict) -> dict:
    """The part of a manifest that may be placed in the model's context."""
    return {k: v for k, v in m.items() if k != "server_bindings"}


def manifest_tokens(tools: list[dict]) -> int:
    return len(json.dumps(tools)) // 4


def raw_tokens(H: Hypergraph, ids: list[str]) -> int:
    return sum(H.contracts[t].tokens for t in ids)


@dataclass
class Pattern:
    prompt: str
    goals: list[dict]
    classes: list[str]
    certificate: dict


@dataclass
class PatternRepository:
    """R: patterns abstracted from certified, executed and confirmed toolkits.

    Tools are replaced by their substitution classes; a pattern seeds decomposition but is
    always re-validated through the full pipeline (it can never bypass the checks)."""

    patterns: list[Pattern] = field(default_factory=list)
    threshold: float = 0.6

    def store(self, prompt: str, goals: list[dict], H: Hypergraph, cert: Certificate, confirmed_by: str) -> bool:
        if confirmed_by not in ("user", "postcondition", "verifier"):
            return False
        classes = sorted({Hypergraph.head_key(H.contracts[t].head) for t in cert.toolkit})
        self.patterns.append(Pattern(prompt, goals, classes, cert.to_dict()))
        return True

    def lookup(self, prompt: str) -> Pattern | None:
        def toks(s: str) -> set[str]:
            return set(re.findall(r"[a-z]+", s.lower()))
        q = toks(prompt)
        best, bs = None, 0.0
        for p in self.patterns:
            t = toks(p.prompt)
            s = len(q & t) / max(1, len(q | t))
            if s > bs:
                best, bs = p, s
        return best if bs >= self.threshold else None
