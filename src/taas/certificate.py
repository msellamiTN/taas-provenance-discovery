"""Valid toolkits and pre-execution certificates (Definition 3, Property 1).

C(K, G, Π) lists the checks (S) sufficiency, (C) consumability, (P) producibility, (E) effect
bound, (L) flow bound, (V) evidence, (M) inclusion-minimality and (B) bridge ratio, each with the
witnesses that discharged it. Counterexamples χ1–χ5 are typed (Section 6.4).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

from .contracts import CapabilityContract
from .effects import violations
from .goals import GoalContract
from .hypergraph import Hypergraph, ModelEdge, ReachResult, effects_of, goal_effect_classes, goal_match, type_serves, uncertain_serves
from .model_profile import ModelProfile
from .policy import Policy
from .types import SemType, subtype

CHI_PRIORITY = {"chi5": 5, "chi2": 4, "chi1": 3, "chi3": 2, "chi4": 1}
CHI_NAMES = {"chi1": "uncovered capability", "chi2": "policy-blocked capability", "chi3": "model overreach",
             "chi4": "model under-use", "chi5": "combination / flow hazard"}


@dataclass
class Counterexample:
    kind: str                 # chi1..chi5
    goal: str | None
    check: str
    witness: dict = field(default_factory=dict)

    def priority(self) -> int:
        return CHI_PRIORITY[self.kind]

    def to_dict(self) -> dict:
        return asdict(self) | {"name": CHI_NAMES[self.kind]}


@dataclass
class Certificate:
    toolkit: list[str]
    checks: dict[str, bool]
    witnesses: dict[str, object]
    regime: str
    cost: float
    util: float
    bridge_ratio: float
    bindings: dict[str, str]

    @property
    def valid(self) -> bool:
        """Whether mandatory pre-execution safety/correctness checks all pass.

        M (inclusion-minimality) and B (bridge diagnostics) are reported separately;
        neither is currently part of the validity predicate. Missing or non-true mandatory
        checks fail closed rather than raising KeyError or accepting truthy non-booleans.
        """
        return all(self.checks.get(k) is True for k in ("S", "C", "P", "E", "L", "V"))

    def to_dict(self) -> dict:
        return asdict(self)


def goal_reached(rr: ReachResult, g: GoalContract, H: Hypergraph | None = None,
                 uncertain: bool = False) -> str | None:
    """Return the witness that discharges g: a type in R with σ <: out(g), or — for an effect
    goal — a fired tool that carries the required effect class (see hypergraph.goal_match)."""
    if goal_effect_classes(g):
        if H is None:
            return None
        for t in sorted(rr.fired):
            if goal_match(H.contracts[t], g):
                return t
        return None
    # a goal outside the model's coverage must be discharged by data a *tool* produced:
    # a prompt-provided or model-written type of the same shape does not count
    need_tool = g.sigma != "native"
    for s in sorted(rr.types, key=str):
        if need_tool and str(s) not in rr.tool_types:
            continue
        if subtype(s, g.out):
            return str(s)
    for s in sorted(rr.types, key=str):
        if need_tool and str(s) not in rr.tool_types:
            continue
        if type_serves(s, g.out):
            return str(s)
    if uncertain and need_tool:
        for s in sorted(rr.types, key=str):
            if str(s) in rr.tool_types and uncertain_serves(s, g.out):
                return f"~{s}"  # uncertain witness, flagged in the certificate
    return None


def consumable(c: CapabilityContract, multimodal: bool) -> bool:
    """(C): out(e) is text/JSON within budget; media is consumable for a multimodal executor or
    when the tool writes an artefact and returns a reference."""
    if c.head.kind == "media":
        return multimodal or any(e.cls == "write" for e in c.eff)
    return True


def _binding_integrity(H: Hypergraph, K: list[str], req_goals: list[GoalContract],
                       s_w: dict[str, str | None], bindings: dict[str, str], rr: ReachResult,
                       model_edges: list[ModelEdge]) -> list[dict]:
    """Validate that every required-goal witness has a provenance-backed binding."""
    model_edge_ids = {m.id for m in model_edges}
    violations_found: list[dict] = []
    for g in req_goals:
        witness = s_w.get(g.id)
        if witness is None:
            violations_found.append({"goal": g.id, "reason": "missing_witness"})
            continue
        typ = witness[1:] if witness.startswith("~") else witness
        binding = bindings.get(g.id)
        derivation = rr.derivations.get(typ)
        if typ in H.contracts:
            if typ not in K or binding != typ:
                violations_found.append({"goal": g.id, "reason": "tool_binding_not_selected", "binding": binding})
        elif typ in rr.tool_types:
            producer = rr.tool_types[typ]
            if producer not in K or binding != producer or derivation is None or derivation.kind != "tool" or derivation.edge != producer:
                violations_found.append({"goal": g.id, "reason": "tool_witness_provenance_mismatch", "binding": binding, "producer": producer})
        elif derivation is not None and derivation.kind == "model":
            if derivation.edge not in model_edge_ids or binding != derivation.edge:
                violations_found.append({"goal": g.id, "reason": "model_binding_provenance_mismatch", "binding": binding, "edge": derivation.edge})
        elif derivation is not None and derivation.kind == "prompt":
            if binding != "-":
                violations_found.append({"goal": g.id, "reason": "prompt_binding_must_be_dash", "binding": binding})
        else:
            violations_found.append({"goal": g.id, "reason": "untraceable_witness", "binding": binding})
    return violations_found


def certify(H: Hypergraph, K: Iterable[str], goals: list[GoalContract], prompt_inputs: list[SemType],
            policy: Policy, model_edges: list[ModelEdge], profile: ModelProfile | None, *, regime: str,
            cost: float, util: float, multimodal: bool = True, conservative_flow: bool = True,
            n_bridge: int = 50, uncertain: bool = False) -> Certificate:
    K = list(K)
    rr = H.reach(K, prompt_inputs, model_edges, profile, n_bridge, policy)
    req_goals = [g for g in goals if not g.optional]
    # (S)
    s_w = {g.id: goal_reached(rr, g, H, uncertain) for g in req_goals}
    S = all(v is not None for v in s_w.values())
    # (C)
    c_w = {t: consumable(H.contracts[t], multimodal) for t in K}
    # (P)
    p_w: dict[str, object] = {}
    P = True
    for t in K:
        c = H.contracts[t]
        ok_args = all(H.tail_satisfied(th, rr.types, profile, n_bridge) is not None for th in c.tail)
        ok_req = policy.credentials is None or all(r in policy.credentials for r in c.req)
        p_w[t] = {"args": ok_args, "prereq": ok_req}
        P &= ok_args and ok_req
    # (E)
    effs = effects_of(H, K)
    bad = violations(effs, policy.allowed)
    pairs = [(a, b, H.is_forbidden(a, b)) for i, a in enumerate(K) for b in K[i + 1:] if H.is_forbidden(a, b)]
    E = not bad and not pairs
    # (L)
    fl = H.flow_violations(K, rr, policy, conservative_flow)
    # (V)
    v_w = {}
    V = True
    for t in K:
        c = H.contracts[t]
        st = {a: c.strength(a, H_trust(H)) for a in policy.required}
        v_w[t] = {"strengths": st, "effect_evidence": c.eff_record.ptype, "hash": c.h}
        if policy.encoding == "positive":
            V &= all(v >= policy.lmin for v in st.values())
    # (M) inclusion-minimality: no e removable without violating (S)–(L)
    removable = []
    for t in K:
        rest = [x for x in K if x != t]
        rr2 = H.reach(rest, prompt_inputs, model_edges, profile, n_bridge, policy)
        if all(goal_reached(rr2, g, H, uncertain) for g in req_goals):
            removable.append(t)
    M = not removable
    # (B) bridge ratio: share of goal outputs reached through model hyperedges
    bindings, via_model, prod = {}, 0, 1.0
    for g in req_goals:
        typ = s_w.get(g.id)
        if typ and typ.startswith("~"):
            typ = typ[1:]
        if typ in H.contracts:
            bindings[g.id] = typ
            continue
        if typ in rr.tool_types and g.sigma != "native":
            bindings[g.id] = rr.tool_types[typ]
            continue
        d = rr.derivations.get(typ) if typ else None
        bindings[g.id] = d.edge if d else "-"
        if d and d.kind == "model":
            via_model += 1
            prod *= d.rho

    # Binding integrity: '-' is accepted only for an explicit prompt derivation.
    binding_violations = _binding_integrity(H, K, req_goals, s_w, bindings, rr, model_edges)
    S = S and not binding_violations
    for b in rr.bridges:
        prod *= b.rho
    beta = via_model / max(1, len(req_goals))
    return Certificate(
        toolkit=K, checks={"S": S, "C": all(c_w.values()), "P": P, "E": E, "L": not fl, "V": V, "M": M, "B": True},
        witnesses={"S": s_w, "C": c_w, "P": p_w, "E": {"effects": sorted(map(str, effs)), "outside_A": list(map(str, bad)),
                                                       "forbidden_pairs": pairs},
                   "L": {"violations": fl, "labels": rr.labels, "mode": "conservative" if conservative_flow else "derivation"},
                   "V": v_w, "M": {"removable": removable},
                   "uncertain_goals": [k for k, v in s_w.items() if v and v.startswith("~")],
                   "binding_integrity": {"valid": not binding_violations, "violations": binding_violations},
                   "B": {"bridge_ratio": beta, "rho_product": prod,
                         "bridges": [asdict(b) for b in rr.bridges]}},
        regime=regime, cost=cost, util=util, bridge_ratio=beta, bindings=bindings)


def H_trust(H: Hypergraph):
    from .provenance import DEFAULT_TRUST
    return getattr(H, "trust", DEFAULT_TRUST)
