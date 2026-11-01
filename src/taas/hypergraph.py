"""Provenance-aware capability hypergraph H = (V, E, λ, eff, L, h, F, ∼) (Definition 5),
reachability reach(K+, X) with its reach graph (Definition 2) and flow-label propagation (check L).

Tail satisfaction (resolution of the paper's "certain supertype" wording, see docs/PAPER_ANALYSIS.md, A3):
a tail type θ is satisfied by the reach set R iff
  (a) some σ ∈ R has σ <: θ with certain typing;
  (b) θ is a pure parameter (kind ∈ FREE_KINDS, no domain): the model writes it from the prompt;
  (c) a class-typed model bridge converts some σ ∈ R into θ: format conversion keeps the domain
      (record:stock[] → table:stock) and extraction yields identifiers/queries/locations/dates/
      numbers from any text-renderable type. Each bridge records its ρ_LLM value.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from .contracts import CapabilityContract
from .effects import Effect, join, label_rank
from .model_profile import ModelProfile
from .policy import Policy
from .types import SemType, parse_type, subtype

FREE_KINDS = frozenset({"number", "boolean", "datetime", "text", "query"})
EXTRACT_TARGETS = frozenset({"identifier", "query", "location", "datetime", "number", "text"})
CONVERT_KINDS = frozenset({"text", "record", "table", "document", "code"})
# kinds the model can render/parse into one another when the domain is the same (format conversion)
DATA_KINDS = frozenset({"text", "record", "table", "document", "location"})


def domain_compatible(s: SemType, theta: SemType) -> bool:
    """σ can be converted into θ by a model edge: same non-empty domain, both data kinds."""
    return (s.domain is not None and s.domain == theta.domain and s.kind in DATA_KINDS
            and theta.kind in DATA_KINDS)


@dataclass(frozen=True)
class ModelEdge:
    """A class-typed model hyperedge e_m^c instantiated for a goal (Cov) or a bridge."""

    cls: str
    tail: tuple[SemType, ...]
    head: SemType
    rho: float
    goal: str | None = None

    @property
    def id(self) -> str:
        return f"LLM::{self.cls}" + (f"[{self.goal}]" if self.goal else "")


@dataclass
class Derivation:
    """One step of the reach graph: edge produced ``head`` from ``inputs``."""

    edge: str
    head: str
    inputs: tuple[str, ...]
    kind: str  # tool | model | bridge | free | prompt
    rho: float = 1.0


@dataclass
class ReachResult:
    types: set[SemType]
    derivations: dict[str, Derivation]
    bridges: list[Derivation]
    labels: dict[str, str] = field(default_factory=dict)
    fired: set[str] = field(default_factory=set)
    tool_types: dict[str, str] = field(default_factory=dict)   # type -> first tool that produced it

    def has(self, theta: SemType | str) -> bool:
        theta = parse_type(theta)
        return any(subtype(s, theta) for s in self.types)


EFFECT_GOAL_CLASSES = frozenset({"write", "delete", "exec", "money"})
SEND_CLASSES = frozenset({"send"})
STRICT_EFFECTS = frozenset({"money", "delete", "exec"})


def goal_effect_classes(goal) -> set[str]:
    """Effects that are the *purpose* of a goal (not mere access effects such as read/egress of a query):
    state-changing classes, plus egress for goals whose class is sending."""
    out = {e.cls for e in getattr(goal, "eff_plus", []) if e.cls in EFFECT_GOAL_CLASSES}
    if getattr(goal, "cls", "") in SEND_CLASSES:
        out |= {e.cls for e in getattr(goal, "eff_plus", []) if e.cls == "egress"} or {"egress"}
    return out


def type_serves(head: SemType, out: SemType) -> bool:
    return subtype(head, out) or domain_compatible(head, out)


def uncertain_serves(head: SemType, out: SemType) -> bool:
    """Uncertain (subsuming) match admitted only by the χ1 repair: same kind, or both data kinds,
    regardless of domain. Recorded as uncertain in the certificate, never as an exact match."""
    return head.kind == out.kind or (head.kind in DATA_KINDS and out.kind in DATA_KINDS)


def goal_match(c: CapabilityContract, goal, uncertain: bool = False) -> bool:
    if uncertain and not goal_effect_classes(goal):
        return type_serves(c.head, goal.out) or uncertain_serves(c.head, goal.out)
    return _goal_match(c, goal)


def _goal_match(c: CapabilityContract, goal) -> bool:
    """Does hyperedge c serve goal g?  Data goals: H(e) <: out(g), or the same domain in a convertible
    data kind (model bridge).  Effect goals: the tool carries the purpose effect (every one of
    money/delete/exec that is required, otherwise at least one), and its output either serves out(g)
    or is a bare confirmation (none/path/text without a conflicting domain)."""
    need = goal_effect_classes(goal)
    if not need:
        return type_serves(c.head, goal.out)
    have = {e.cls for e in c.eff}
    if not (need & have) or not (need & STRICT_EFFECTS) <= have:
        return False
    if type_serves(c.head, goal.out) or goal.out.kind in ("none", "path"):
        return True
    return c.head.kind in ("none", "path", "text") and (c.head.domain is None or goal.out.domain is None
                                                        or c.head.domain == goal.out.domain)


@dataclass
class Hypergraph:
    contracts: dict[str, CapabilityContract] = field(default_factory=dict)
    forbidden: dict[tuple[str, str], str] = field(default_factory=dict)       # F with reason
    admin_forbidden: dict[tuple[str, str], str] = field(default_factory=dict)
    subst: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # ∼ by head key
    kappa_min: float = 0.5

    # ---------------------------------------------------------------- update
    def add(self, c: CapabilityContract, policy: Policy | None = None) -> None:
        self.remove(c.tool)
        self.contracts[c.tool] = c
        self.subst[self.head_key(c.head)].add(c.tool)
        for other in self.contracts.values():
            if other.tool != c.tool:
                self._pair(c, other, policy)
                self._pair(other, c, policy)

    def remove(self, tool: str) -> None:
        c = self.contracts.pop(tool, None)
        if c is None:
            return
        self.subst[self.head_key(c.head)].discard(tool)
        for k in [k for k in self.forbidden if tool in k]:
            del self.forbidden[k]

    @staticmethod
    def head_key(t: SemType) -> str:
        return str(SemType(t.kind, t.domain, t.collection))

    def _pair(self, a: CapabilityContract, b: CapabilityContract, policy: Policy | None) -> None:
        templates = policy.forbidden_pairs if policy else (("private_read", "egress_any"),)
        for x, y in templates:
            if _matches(a, x) and _matches(b, y):
                key = tuple(sorted((a.tool, b.tool)))
                self.forbidden[key] = f"{x}+{y}: exfiltration"  # type: ignore[index]
        key = tuple(sorted((a.tool, b.tool)))
        if key in self.admin_forbidden:
            self.forbidden[key] = self.admin_forbidden[key]  # type: ignore[index]

    def rebuild_pairs(self, policy: Policy | None = None) -> None:
        self.forbidden = {}
        cs = list(self.contracts.values())
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                self._pair(a, b, policy)
                self._pair(b, a, policy)

    def is_forbidden(self, a: str, b: str) -> str | None:
        return self.forbidden.get(tuple(sorted((a, b))))  # type: ignore[arg-type]

    def substitutes(self, tool: str) -> set[str]:
        c = self.contracts[tool]
        key = self.head_key(c.head)
        out = set()
        for k, ts in self.subst.items():
            t = parse_type(k)
            if subtype(t, c.head) or subtype(c.head, t) or k == key:
                out |= ts
        return out - {tool}

    # ----------------------------------------------------------------- reach
    def tail_satisfied(self, theta: SemType, R: set[SemType], profile: ModelProfile | None,
                       n: int = 50, rho_min: float = 0.0) -> Derivation | None:
        for s in R:
            if subtype(s, theta):
                return Derivation("subtype", str(theta), (str(s),), "subtype")
        if theta.kind in FREE_KINDS and theta.domain is None:
            return Derivation("LLM::write", str(theta), ("text",), "free", 1.0)
        if profile is None:
            return None
        best: Derivation | None = None
        for s in R:
            if not s.is_text_renderable:
                continue
            if theta.kind in EXTRACT_TARGETS and not theta.collection:
                rho = profile.rho("extract", n)
                if rho >= max(profile.tau, rho_min) and (best is None or rho > best.rho):
                    best = Derivation("LLM::extract", str(theta), (str(s),), "bridge", rho)
            if domain_compatible(s, theta) or (theta.kind in CONVERT_KINDS and s.kind in CONVERT_KINDS
                                                and s.domain is not None and s.domain == theta.domain):
                rho = profile.rho("convert_format", n)
                if rho >= max(profile.tau, rho_min) and (best is None or rho > best.rho):
                    best = Derivation("LLM::convert_format", str(theta), (str(s),), "bridge", rho)
        return best

    def reach(self, K: Iterable[str], X: Iterable[SemType | str], model_edges: Iterable[ModelEdge] = (),
              profile: ModelProfile | None = None, n_bridge: int = 50, policy: Policy | None = None,
              conservative_flow: bool = True) -> ReachResult:
        """Least fixpoint of Definition 2 over K+ = K ∪ {model edges}."""
        prompt_label = policy.prompt_label if policy else "public"
        R: set[SemType] = {parse_type(x) for x in X}
        der: dict[str, Derivation] = {str(x): Derivation("prompt", str(x), (), "prompt") for x in R}
        labels: dict[str, str] = {str(x): prompt_label for x in R}
        bridges: list[Derivation] = []
        edges: list[tuple[str, tuple[SemType, ...], SemType, object]] = []
        for t in K:
            c = self.contracts[t]
            edges.append((t, c.tail, c.head, c))
        for m in model_edges:
            edges.append((m.id, m.tail, m.head, m))
        fired: set[str] = set()
        tool_types: dict[str, str] = {}
        changed = True
        while changed:
            changed = False
            for eid, tail, head, obj in edges:
                if eid in fired:
                    continue
                sats = []
                ok = True
                for th in tail:
                    d = self.tail_satisfied(th, R, profile, n_bridge)
                    if d is None:
                        ok = False
                        break
                    sats.append(d)
                if not ok:
                    continue
                fired.add(eid)
                in_labels = []
                for d in sats:
                    src = d.inputs[0] if d.inputs else "text"
                    in_labels.append(labels.get(src, prompt_label))
                    if d.kind == "bridge":
                        bridges.append(d)
                if isinstance(obj, CapabilityContract):
                    out_label = join(in_labels + [obj.flow.source_label])
                    out_label = self._declassify(obj, out_label, policy)
                    kind = "tool"
                    rho = 1.0 - obj.qos.fail
                else:
                    out_label = join(in_labels) if in_labels else prompt_label
                    kind = "model"
                    rho = obj.rho  # type: ignore[union-attr]
                hk = str(head)
                if kind == "tool":
                    tool_types.setdefault(hk, eid)
                if head not in R:
                    R.add(head)
                    changed = True
                if hk not in der or (kind == "tool" and der[hk].kind == "model"):
                    der[hk] = Derivation(eid, hk, tuple(d.inputs[0] if d.inputs else "" for d in sats), kind, rho)
                labels[hk] = join([labels.get(hk, "public"), out_label]) if hk in labels else out_label
        return ReachResult(R, der, bridges, labels, {f for f in fired if not f.startswith("LLM::")}, tool_types)

    def _declassify(self, c: CapabilityContract, label: str, policy: Policy | None) -> str:
        if not policy:
            return label
        for rule in policy.declass:
            if label == rule.label_from and rule.authorises(c.tool, c.tool_class, c.eff_strength(), rule.min_records):
                return rule.label_to
        return label

    # ------------------------------------------------------------ flow check
    def flow_violations(self, K: Iterable[str], rr: ReachResult, policy: Policy,
                        conservative: bool = True) -> list[dict]:
        """Check (L): no label above the threshold flows into an edge with an egress effect.

        * derivation mode: the label reaching an egress tool is the join of the labels of the
          types that satisfy its tails in the recorded reach graph;
        * conservative mode (default): every tool result returns to the model's context, and the
          model can write any context content into any text-renderable argument, so an egress
          tool with such an argument receives the join of all labels in the context.
        """
        thr = label_rank(policy.egress_threshold)
        ctx = join(list(rr.labels.values()))
        out = []
        for t in K:
            c = self.contracts[t]
            if not any(e.cls == "egress" for e in c.eff):
                continue
            # every argument, required or optional, can carry context data
            if conservative and any(a.type.is_text_renderable for a in c.args):
                lab = ctx
            else:
                ins = []
                for th in c.tail:
                    for s in rr.types:
                        if subtype(s, th):
                            ins.append(rr.labels.get(str(s), "public"))
                lab = join(ins) if ins else "public"
            if label_rank(lab) > thr:
                out.append({"tool": t, "label": lab, "threshold": policy.egress_threshold,
                            "mode": "conservative" if conservative else "derivation"})
        return out


def _matches(c: CapabilityContract, template: str) -> bool:
    if template == "private_read":
        return c.flow.source_label in ("private", "secret")
    if template == "egress_any":
        return any(e.cls == "egress" and e.scope in ("*", "") for e in c.eff)
    if template.startswith("effect:"):
        cls = template.split(":", 1)[1]
        return any(e.cls == cls for e in c.eff)
    return False


def effects_of(H: Hypergraph, K: Iterable[str]) -> frozenset[Effect]:
    out: set[Effect] = set()
    for t in K:
        out |= H.contracts[t].eff
    return frozenset(out)
