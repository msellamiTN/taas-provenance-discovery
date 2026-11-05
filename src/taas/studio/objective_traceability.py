"""Compose Objective-to-Skill traceability provenance.

This module links the deterministic artifacts that already exist in the
prepare response into one inspectable record:

  objective clause span -> derived outcome -> GoalSpec goal
                        -> triggered skill (exact pin) -> clause span

All links are lexical and structural only. A skill selected because a declared
trigger phrase occurs inside a clause is *associated* with that clause — never
asserted to have produced the outcome, the goal, or any capability. Semantic
correctness remains unverified and human review stays mandatory.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_SCHEMA = "taas.objective-skill-traceability/v1"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _trigger_occurrences(phrase: str, objective: str) -> list[dict[str, int]]:
    """Return every case-insensitive occurrence span of a trigger phrase.

    Offsets are computed against the original objective text, matching the
    substring policy used by Agent Intelligence Context selection.
    """
    if not phrase.strip():
        return []
    return [
        {"start": match.start(), "end": match.end()}
        for match in re.finditer(re.escape(phrase), objective, flags=re.IGNORECASE)
    ]


def _clause_for_offset(clauses: list[dict[str, Any]], offset: int) -> str | None:
    for clause in clauses:
        span = clause.get("span", {})
        start, end = span.get("start"), span.get("end")
        if isinstance(start, int) and isinstance(end, int) and start <= offset < end:
            return clause.get("id")
    return None


def build_objective_skill_traceability(
    *,
    objective: str,
    contract_v3: dict[str, Any] | None,
    coverage: dict[str, Any] | None,
    agent_context_trace: dict[str, Any] | None,
    goal_spec: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the unified clause -> outcome -> goal -> skill provenance record."""
    clauses = list((contract_v3 or {}).get("clauses", []))
    contract_outcomes = {
        item.get("id"): item for item in (contract_v3 or {}).get("outcomes", [])
        if isinstance(item, dict)
    }
    coverage_outcomes = {
        item.get("id"): item for item in (coverage or {}).get("outcomes", [])
        if isinstance(item, dict)
    }
    goals = {
        goal.get("id"): goal for goal in (goal_spec or {}).get("goals", [])
        if isinstance(goal, dict)
    }
    skill_traces = list((agent_context_trace or {}).get("skills", []))

    skill_selection: list[dict[str, Any]] = []
    skills_by_clause: dict[str, list[str]] = {}
    for trace in skill_traces:
        if not isinstance(trace, dict):
            continue
        skill_id = str(trace.get("id", ""))
        matched: list[dict[str, Any]] = []
        for phrase in trace.get("matched_triggers", []) or []:
            occurrences = _trigger_occurrences(str(phrase), objective)
            matched.append({
                "phrase": str(phrase),
                "occurrences": [
                    {
                        **occ,
                        "clause_ref": _clause_for_offset(clauses, occ["start"]),
                    }
                    for occ in occurrences
                ],
            })
            for occ in occurrences:
                clause_ref = _clause_for_offset(clauses, occ["start"])
                if clause_ref:
                    skills_by_clause.setdefault(clause_ref, []).append(skill_id)
        entry = {
            "skill_id": skill_id,
            "version": trace.get("version"),
            "source": trace.get("source", "embedded"),
            "selected": bool(trace.get("selected")),
            "instructions_sha256": trace.get("instructions_sha256"),
            "registry_manifest_sha256": trace.get("registry_manifest_sha256"),
            "selection_policy": trace.get("selection_policy"),
            "matched_triggers": matched,
        }
        skill_selection.append(entry)

    outcome_provenance: list[dict[str, Any]] = []
    for outcome in (contract_v3 or {}).get("outcomes", []):
        if not isinstance(outcome, dict):
            continue
        outcome_id = outcome.get("id")
        clause_ref = outcome.get("clause_ref")
        covered = coverage_outcomes.get(outcome_id, {})
        outcome_provenance.append({
            "outcome_id": outcome_id,
            "goal_class": outcome.get("goal_class"),
            "clause_ref": clause_ref,
            "source_evidence": list(outcome.get("source_evidence", [])),
            "coverage_status": covered.get("status", "not_assessed"),
            "covered_by_goal_ids": list(covered.get("goal_ids", [])),
            "skills_triggered_in_clause": sorted(set(skills_by_clause.get(clause_ref, []))),
        })

    goal_provenance: list[dict[str, Any]] = []
    for provenance in outcome_provenance:
        for goal_id in provenance["covered_by_goal_ids"]:
            goal = goals.get(goal_id, {})
            goal_provenance.append({
                "goal_id": goal_id,
                "goal_class": goal.get("class"),
                "linked_outcome_id": provenance["outcome_id"],
                "clause_ref": provenance["clause_ref"],
                "skills_triggered_in_clause": provenance["skills_triggered_in_clause"],
            })

    return {
        "schema": _SCHEMA,
        "objective_sha256": _sha256(objective),
        "clauses": [
            {
                "clause_id": clause.get("id"),
                "span": clause.get("span"),
                "outcome_refs": list(clause.get("outcome_refs", [])),
            }
            for clause in clauses
        ],
        "outcome_provenance": outcome_provenance,
        "skill_selection": skill_selection,
        "goal_provenance": goal_provenance,
        "coverage_summary": (coverage or {}).get("summary"),
        "agent_context_status": (agent_context_trace or {}).get("status", "not_configured"),
        "provenance_scope": "lexical_trigger_and_clause_binding_only_not_semantic_proof",
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }
