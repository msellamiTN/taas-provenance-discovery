"""Read-only diagnostics for the TaaS Core discovery pipeline.

This module explains registry/index, policy eligibility and retrieval outcomes. It does
not modify policy, infer authorization, invoke tools, or certify semantic correctness.
"""
from __future__ import annotations

from typing import Any

from taas.composer import eligible_set
from taas.provenance import NEGATIVE_PROPS, POSITIVE_PROPS


def build_discovery_diagnostics(engine: Any, policy: Any,
                                composition_stats: dict | None = None,
                                toolkit: list[str] | None = None,
                                abstained: bool = False) -> dict[str, Any]:
    index = getattr(engine, "index", None)
    graph = getattr(engine, "H", None)
    contracts = getattr(graph, "contracts", {}) if graph is not None else {}
    if index is None:
        return {"schema": "taas.discovery-diagnostics/v1", "available": False,
                "reason": "engine_index_not_exposed"}

    live_ids = index.to_ids(index.live)
    eligible_ids = eligible_set(index, policy)
    visible = policy.visible
    per_tool = []
    for tool_id in live_ids:
        contract = contracts.get(tool_id)
        strengths = dict(index.strengths.get(tool_id, {}))
        exclusions = []
        if visible is not None and tool_id not in visible:
            exclusions.append({"stage": "visibility", "reason": "tool_not_in_policy_visible_set"})
        if policy.encoding == "positive":
            for prop in sorted(policy.required):
                value = strengths.get(prop, 0.0)
                if value < policy.lmin:
                    exclusions.append({"stage": "positive_policy", "property": prop,
                                       "strength": value, "required_strength": policy.lmin})
        else:
            for prop in sorted(policy.forbidden):
                value = strengths.get(prop, 0.0)
                if value >= policy.lmin:
                    exclusions.append({"stage": "closed_world_policy", "property": prop,
                                       "strength": value, "forbidden_at_strength": policy.lmin})
        per_tool.append({
            "tool_id": tool_id,
            "indexed_live": True,
            "eligible": tool_id in eligible_ids,
            "exclusions": exclusions,
            "property_strengths": {key: strengths.get(key, 0.0)
                                   for key in (*POSITIVE_PROPS, *NEGATIVE_PROPS)},
            "effects": sorted(map(str, contract.eff)) if contract is not None else [],
            "input_types": [str(arg.type) for arg in contract.args] if contract is not None else [],
            "output_type": str(contract.head) if contract is not None else None,
            "effect_evidence": ({"type": contract.eff_record.ptype,
                                 "method": contract.eff_record.method}
                                if contract is not None else None),
            "annotation_hints_present": bool(contract.annotations) if contract is not None else False,
        })
    stats = composition_stats or {}
    observed_eligible = stats.get("eligible")
    candidate_count = stats.get("candidates")
    if toolkit is not None and not abstained:
        stage = "selected_pending_human_review"
    elif not live_ids:
        stage = "registry_or_index_empty"
    elif not eligible_ids:
        stage = "policy_eligibility"
    elif candidate_count == 0:
        stage = "candidate_retrieval_or_type_matching"
    else:
        stage = "composition_or_certificate"
    return {
        "schema": "taas.discovery-diagnostics/v1",
        "available": True,
        "pipeline_stage": stage,
        "registry_contract_count": len(contracts),
        "index_live_count": len(live_ids),
        "index_slot_count": len(index.tool_at),
        "policy": {
            "encoding": policy.encoding,
            "required_properties": sorted(policy.required),
            "forbidden_properties": sorted(policy.forbidden),
            "minimum_evidence_strength": policy.lmin,
            "visible_tool_count": len(visible) if visible is not None else None,
            "allowed_effects": sorted(map(str, policy.allowed)),
        },
        "eligibility": {
            "eligible_count": len(eligible_ids),
            "eligible_tool_ids": eligible_ids,
            "composition_reported_eligible_count": observed_eligible,
            "composition_count_matches_preflight": (
                observed_eligible == len(eligible_ids) if observed_eligible is not None else None
            ),
        },
        "candidate_retrieval": {"candidate_count": candidate_count,
                                "per_goal": stats.get("per_goal", {})},
        "tools": per_tool,
        "selected_tools": list(toolkit or []),
        "execution_performed": False,
        "semantic_correctness_verified": False,
    }
