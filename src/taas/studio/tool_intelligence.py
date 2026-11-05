"""Tool Intelligence v1 — deterministic per-candidate intelligence for discovery.

Composes the discovery run's already-computed artifacts (contracts, per-goal
candidate retrieval, policy, property strengths, selection certificate) into an
inspectable per-tool record:

  goal served -> capability match (exact/uncertain) -> required inputs ->
  effect profile vs policy -> composition neighbours -> assurance binding

All matches are *structural* — semantic-type and effect compatibility — never
semantic correctness. Selection certificates bind the selection, not any claim
that a tool ran. Nothing here invokes tools or grants rights.
"""
from __future__ import annotations

from typing import Any, Mapping

from taas.hypergraph import goal_match, type_serves

SCHEMA = "taas.tool-intelligence/v1"
_BOUNDS = {"tools": 64, "goals": 32}


def _match_kind(contract: Any, goal: Any) -> str:
    """Classify output compatibility exactly as the composer does."""
    try:
        if goal_match(contract, goal, uncertain=False):
            return "exact"
        if goal_match(contract, goal, uncertain=True):
            return "uncertain"
    except Exception:
        pass
    return "none"


def _input_detail(contract: Any, goal: Any) -> dict[str, Any]:
    """Structural check: which required input types the goal's inputs serve."""
    goal_inputs = [str(item) for item in getattr(goal, "inputs", []) or []]
    satisfied, missing = [], []
    for arg in getattr(contract, "args", ()) or ():
        if not getattr(arg, "required", False):
            continue
        arg_type = str(arg.type)
        served_by = [g for g in goal_inputs if type_serves(g, arg_type)]
        entry = {"argument": arg.name, "type": arg_type, "served_by": served_by}
        (satisfied if served_by else missing).append(entry)
    return {
        "required_inputs": satisfied + missing,
        "missing_inputs": [entry["type"] for entry in missing],
        "all_required_inputs_served": not missing,
    }


def build_tool_intelligence(
    *,
    contracts: Mapping[str, Any],
    diagnostics: dict[str, Any],
    goals: list[Any],
    toolkit: list[str] | None,
    certificate: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the per-candidate intelligence record for one discovery run."""
    diag_tools = diagnostics.get("tools", [])
    policy = diagnostics.get("policy", {})
    per_goal = (diagnostics.get("candidate_retrieval", {}) or {}).get("per_goal", {})
    allowed_effects = set(policy.get("allowed_effects", []))
    threshold = policy.get("minimum_evidence_strength")
    selected = set(toolkit or [])
    certified_selection = certificate is not None and bool(selected)

    if len(diag_tools) > _BOUNDS["tools"] or len(goals) > _BOUNDS["goals"]:
        raise ValueError("tool intelligence inputs exceed v1 bounds")

    goals_by_id = {getattr(g, "id", None): g for g in goals}
    output_types = {t.get("tool_id"): t.get("output_type") for t in diag_tools}
    input_types = {t.get("tool_id"): set(t.get("input_types", [])) for t in diag_tools}

    tools: list[dict[str, Any]] = []
    for entry in diag_tools:
        tool_id = entry.get("tool_id")
        contract = contracts.get(tool_id)
        serves = sorted(gid for gid, ids in per_goal.items()
                        if gid != "_derived" and tool_id in ids)
        derived_candidate = tool_id in per_goal.get("_derived", [])

        capability = []
        for goal_id in serves:
            goal = goals_by_id.get(goal_id)
            if goal is None or contract is None:
                capability.append({"goal_id": goal_id, "match": "unknown"})
                continue
            capability.append({
                "goal_id": goal_id,
                "match": _match_kind(contract, goal),
                "goal_out": str(getattr(goal, "out", "")),
                "tool_output_type": entry.get("output_type"),
                **_input_detail(contract, goal),
            })

        effects = list(entry.get("effects", []))
        strengths = entry.get("property_strengths", {}) or {}
        out_type = entry.get("output_type")
        feeds = sorted(
            other for other, ins in input_types.items()
            if other != tool_id and out_type and out_type in ins
        )
        fed_by = sorted(
            other for other, out in output_types.items()
            if other != tool_id and out and out in input_types.get(tool_id, set())
        )
        tools.append({
            "tool_id": tool_id,
            "indexed_live": bool(entry.get("indexed_live")),
            "eligible": bool(entry.get("eligible")),
            "selected": tool_id in selected,
            "serves_goals": serves,
            "derived_candidate": derived_candidate,
            "capability_match": capability,
            "effect_profile": {
                "effects": effects,
                "policy_allowed": all(e in allowed_effects for e in effects),
                "forbidden_with": [x.get("tool_id") for x in entry.get("exclusions", [])],
            },
            "evidence": {
                "effect_evidence": entry.get("effect_evidence"),
                "property_strengths": strengths,
                "max_property_strength": max(strengths.values(), default=None),
                "policy_minimum_evidence_strength": threshold,
                "policy_evidence_met": bool(entry.get("eligible")),
            },
            "composition": {"feeds": feeds, "fed_by": fed_by},
            "assurance": {
                "covered_by_selection_certificate": certified_selection and tool_id in selected,
                "assessor_claim_truth_verified": False,
            },
            "structural_match_only": True,
            "semantic_correctness_verified": False,
        })

    tools.sort(key=lambda item: item["tool_id"])
    return {
        "schema": SCHEMA,
        "tools": tools,
        "summary": {
            "tool_count": len(tools),
            "eligible_count": sum(1 for t in tools if t["eligible"]),
            "selected_count": len(selected),
            "composition_edge_count": sum(len(t["composition"]["feeds"]) for t in tools),
            "goals_with_candidates": sorted(g for g in per_goal if g != "_derived"),
        },
        "match_semantics": "structural_type_and_effect_compatibility_only",
        "semantic_correctness_verified": False,
        "tools_invoked": False,
        "execution_performed": False,
    }
