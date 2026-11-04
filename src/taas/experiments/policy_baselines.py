"""Policy/effect baseline controls for E4-E7.

These functions use only published tool metadata, never evaluator reference labels.
"""
from __future__ import annotations

import re
from typing import Sequence

from taas.data.registries import RawTool
from taas.effects import lexical_effects, modifies_state


READ_VERBS = re.compile(
    r"(?:^|[_\-\s.])(read|list|get|fetch|retrieve|search|find|query|lookup|browse|inspect|view|show|describe)(?:$|[_\-\s.])",
    re.IGNORECASE,
)


def _annotation_stats(tools: Sequence[RawTool]) -> dict:
    states = {"true": 0, "false": 0, "missing": 0, "invalid": 0}
    for tool in tools:
        value = (tool.annotations or {}).get("readOnlyHint", None)
        if value is True:
            states["true"] += 1
        elif value is False:
            states["false"] += 1
        elif value is None:
            states["missing"] += 1
        else:
            states["invalid"] += 1
    return states


def _lexical_has_positive_read_cue(tool: RawTool) -> bool:
    text = f"{tool.name} {tool.description}"
    return bool(READ_VERBS.search(" " + text + " "))


def run_policy_baseline(baseline_id: str, tools: Sequence[RawTool]) -> dict:
    """Apply a declared/lexical eligibility control.

    MCP-defaults deliberately does not turn annotations into an access-control
    decision: the catalogue remains visible while annotation claims are surfaced
    as untrusted hints. The closed-world filter instead requires readOnlyHint=true.
    """
    allowed_ids: list[str] = []
    rejected_ids: list[str] = []
    reasons: dict[str, str] = {}
    annotation_stats = _annotation_stats(tools)

    if baseline_id == "mcp_default_annotations":
        allowed_ids = [tool.id for tool in tools]
        for tool in tools:
            hint = (tool.annotations or {}).get("readOnlyHint", None)
            reasons[tool.id] = ("declares_read_only" if hint is True else
                                "declares_not_read_only" if hint is False else
                                "read_only_hint_unspecified")
        method = "Default MCP client interpretation: expose discovered tools and retain readOnlyHint as an untrusted hint, not an eligibility proof."
        status = "completed"
    elif baseline_id == "closed_world_annotations":
        for tool in tools:
            if (tool.annotations or {}).get("readOnlyHint") is True:
                allowed_ids.append(tool.id)
                reasons[tool.id] = "positive_read_only_hint_present"
            else:
                rejected_ids.append(tool.id)
                reasons[tool.id] = "missing_or_false_read_only_hint"
        method = "Closed-world metadata filter: only an explicit readOnlyHint=true declaration remains eligible."
        status = "completed"
    elif baseline_id == "lexical_positive":
        for tool in tools:
            effects = lexical_effects(tool.name, tool.description,
                                      list(((tool.input_schema or {}).get("properties") or {}).keys()))
            if _lexical_has_positive_read_cue(tool) and not modifies_state(effects):
                allowed_ids.append(tool.id)
                reasons[tool.id] = "positive_read_verb_and_no_detected_state_modification"
            else:
                rejected_ids.append(tool.id)
                reasons[tool.id] = "no_positive_read_cue_or_state_modification_detected"
        method = "Positive lexical filter: require an explicit read/list/get/search/fetch-style cue and no detected persistent state modification."
        status = "completed"
    elif baseline_id == "lexical_closed_world":
        for tool in tools:
            effects = lexical_effects(tool.name, tool.description,
                                      list(((tool.input_schema or {}).get("properties") or {}).keys()))
            if modifies_state(effects):
                rejected_ids.append(tool.id)
                reasons[tool.id] = "lexically_detected_state_modification"
            else:
                allowed_ids.append(tool.id)
                reasons[tool.id] = "no_state_modification_cue_detected_unknown_treated_as_safe"
        method = "Closed-world lexical filter: reject explicit write/delete/execute/money cues; absence of such a cue is treated as safe."
        status = "completed"
    elif baseline_id == "verified_evidence":
        return {
            "baseline_id": baseline_id,
            "status": "blocked_missing_independent_evidence_store",
            "selected_tool_ids": [],
            "rejected_tool_ids": [],
            "annotation_counts": annotation_stats,
            "evaluator_labels_read": False,
            "reason": "This adapter requires hash-bound probe/attestation evidence from the independent evidence pipeline. Published annotations and silver labels are not substituted.",
        }
    else:
        raise KeyError(f"Unsupported policy baseline: {baseline_id}")

    return {
        "baseline_id": baseline_id,
        "status": status,
        "selected_tool_ids": allowed_ids,
        "rejected_tool_ids": rejected_ids,
        "eligible_count": len(allowed_ids),
        "candidate_count": len(tools),
        "eligible_share": len(allowed_ids) / len(tools) if tools else 0.0,
        "per_tool_reason": reasons,
        "annotation_counts": annotation_stats,
        "method": method,
        "annotations_treated_as_verified_evidence": False,
        "evaluator_labels_read": False,
    }
