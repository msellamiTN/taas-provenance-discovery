"""Independent, offline checker for PaMCP pre-execution certificates.

The checker recomputes the six mandatory Definition 3 predicates from frozen inputs.
It does not trust Certificate.valid or the producer's checks/witnesses. It does not
start servers, invoke tools, or establish runtime behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contracts import CapabilityContract
from .effects import violations
from .goals import GoalContract
from .hypergraph import (
    Hypergraph, ModelEdge, ReachResult, effects_of, goal_effect_classes,
    goal_match, type_serves, uncertain_serves,
)
from .model_profile import ModelProfile
from .policy import Policy
from .provenance import DEFAULT_TRUST
from .types import SemType, subtype


MANDATORY = ("S", "C", "P", "E", "L", "V")


@dataclass(frozen=True)
class CertificateAudit:
    recomputed: dict[str, bool]
    reported: dict[str, bool | None]
    matches: dict[str, bool]
    valid: bool
    mismatches: tuple[str, ...]
    unknown_tools: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "recomputed": dict(self.recomputed),
            "reported": dict(self.reported),
            "matches": dict(self.matches),
            "valid": self.valid,
            "mismatches": list(self.mismatches),
            "unknown_tools": list(self.unknown_tools),
            "scope": "offline pre-execution contract audit; not runtime verification",
        }


def _goal_witness(rr: ReachResult, goal: GoalContract, graph: Hypergraph,
                  uncertain: bool) -> str | None:
    if goal_effect_classes(goal):
        for tool in sorted(rr.fired):
            if tool in graph.contracts and goal_match(graph.contracts[tool], goal):
                return tool
        return None
    need_tool = goal.sigma != "native"
    for value in sorted(rr.types, key=str):
        if need_tool and str(value) not in rr.tool_types:
            continue
        if subtype(value, goal.out):
            return str(value)
    for value in sorted(rr.types, key=str):
        if need_tool and str(value) not in rr.tool_types:
            continue
        if type_serves(value, goal.out):
            return str(value)
    if uncertain and need_tool:
        for value in sorted(rr.types, key=str):
            if str(value) in rr.tool_types and uncertain_serves(value, goal.out):
                return f"~{value}"
    return None


def _binding_violations(graph: Hypergraph, toolkit: list[str],
                         goals: list[GoalContract], witnesses: dict[str, str | None],
                         bindings: dict[str, str], reach: ReachResult,
                         model_edges: list[ModelEdge]) -> list[dict]:
    """Independently check provenance for each required-goal witness."""
    model_ids = {edge.id for edge in model_edges}
    errors = []
    for goal in goals:
        witness = witnesses.get(goal.id)
        if witness is None:
            errors.append({"goal": goal.id, "reason": "missing_witness"})
            continue
        value = witness[1:] if witness.startswith("~") else witness
        binding = bindings.get(goal.id)
        derivation = reach.derivations.get(value)
        if value in graph.contracts:
            if value not in toolkit or binding != value:
                errors.append({"goal": goal.id, "reason": "tool_binding_not_selected"})
        elif value in reach.tool_types:
            producer = reach.tool_types[value]
            if (producer not in toolkit or binding != producer or derivation is None
                    or derivation.kind != "tool" or derivation.edge != producer):
                errors.append({"goal": goal.id, "reason": "tool_witness_provenance_mismatch"})
        elif derivation is not None and derivation.kind == "model":
            if derivation.edge not in model_ids or binding != derivation.edge:
                errors.append({"goal": goal.id, "reason": "model_binding_provenance_mismatch"})
        elif derivation is not None and derivation.kind == "prompt":
            if binding != "-":
                errors.append({"goal": goal.id, "reason": "prompt_binding_must_be_dash"})
        else:
            errors.append({"goal": goal.id, "reason": "untraceable_witness"})
    return errors


def audit_certificate(
    certificate,
    graph: Hypergraph,
    goals: Iterable[GoalContract],
    prompt_inputs: Iterable[SemType],
    policy: Policy,
    model_edges: Iterable[ModelEdge] = (),
    profile: ModelProfile | None = None,
    *,
    multimodal: bool = True,
    conservative_flow: bool = True,
    n_bridge: int = 50,
    uncertain: bool = False,
) -> CertificateAudit:
    """Recompute S,C,P,E,L,V and compare them with the submitted certificate.

    M and B are intentionally not folded into validity: Definition 3's implementation
    reports them as diagnostics, while Certificate.valid requires S,C,P,E,L,V.
    """
    toolkit = list(certificate.toolkit)
    unknown = tuple(sorted(set(toolkit) - set(graph.contracts)))
    if unknown:
        reported = {key: certificate.checks.get(key) for key in MANDATORY}
        return CertificateAudit(
            recomputed={key: False for key in MANDATORY},
            reported=reported, matches={key: False for key in MANDATORY},
            valid=False, mismatches=MANDATORY, unknown_tools=unknown,
        )
    if len(toolkit) != len(set(toolkit)):
        # Duplicate selections are malformed rather than silently normalized.
        reported = {key: certificate.checks.get(key) for key in MANDATORY}
        return CertificateAudit(
            recomputed={key: False for key in MANDATORY},
            reported=reported, matches={key: False for key in MANDATORY},
            valid=False, mismatches=MANDATORY, unknown_tools=(),
        )

    goals = list(goals)
    required = [goal for goal in goals if not goal.optional]
    model_edges = list(model_edges)
    reach = graph.reach(toolkit, list(prompt_inputs), model_edges, profile,
                        n_bridge, policy, conservative_flow)

    # S — every required goal has an independently recomputed witness.
    witnesses = {goal.id: _goal_witness(reach, goal, graph, uncertain) for goal in required}
    binding_errors = _binding_violations(\n        graph, toolkit, required, witnesses, certificate.bindings, reach, model_edges\n    )\n    sufficiency = all(value is not None for value in witnesses.values()) and not binding_errors

    # C — selected tool outputs are consumable by the configured executor.
    consumability = all(
        graph.contracts[tool].head.kind != "media"
        or multimodal
        or any(effect.cls == "write" for effect in graph.contracts[tool].eff)
        for tool in toolkit
    )

    # P — all required inputs can be supplied and credential prerequisites are held.
    producibility = True
    for tool in toolkit:
        contract = graph.contracts[tool]
        args_ok = all(
            graph.tail_satisfied(arg, reach.types, profile, n_bridge) is not None
            for arg in contract.tail
        )
        credentials_ok = (
            policy.credentials is None
            or all(item in policy.credentials for item in contract.req)
        )
        producibility = producibility and args_ok and credentials_ok

    # E — scoped effects are allowed and no forbidden pair is selected.
    all_effects = effects_of(graph, toolkit)
    no_effect_violation = not violations(all_effects, policy.allowed)
    no_forbidden_pair = all(
        graph.is_forbidden(left, right) is None
        for index, left in enumerate(toolkit)
        for right in toolkit[index + 1:]
    )
    effect_bound = no_effect_violation and no_forbidden_pair

    # L — information-flow constraints use the configured flow-check mode.
    flow_bound = not graph.flow_violations(toolkit, reach, policy, conservative_flow)

    # V — positive-encoding required properties meet the trust threshold.
    trust = getattr(graph, "trust", DEFAULT_TRUST)
    evidence_bound = True
    if policy.encoding == "positive":
        for tool in toolkit:
            contract: CapabilityContract = graph.contracts[tool]
            strengths = [
                max((trust.strength(prop, record)
                     for record in contract.props.get(prop, [])), default=0.0)
                for prop in policy.required
            ]
            if not all(value >= policy.lmin for value in strengths):
                evidence_bound = False
                break

    recomputed = {
        "S": sufficiency,
        "C": consumability,
        "P": producibility,
        "E": effect_bound,
        "L": flow_bound,
        "V": evidence_bound,
    }
    reported = {key: certificate.checks.get(key) for key in MANDATORY}
    matches = {key: reported[key] is recomputed[key] for key in MANDATORY}
    mismatches = tuple(key for key in MANDATORY if not matches[key])
    return CertificateAudit(
        recomputed=recomputed, reported=reported, matches=matches,
        valid=all(recomputed.values()) and not mismatches,
        mismatches=mismatches, unknown_tools=(),
    )
