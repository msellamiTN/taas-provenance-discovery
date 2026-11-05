from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio.api import AgentDecomposeRequest
from taas.studio.objective_traceability import build_objective_skill_traceability


OBJECTIVE = (
    "Find the year difference between two independently sourced dates. "
    "Then report the result."
)

CONTRACT_V3 = {
    "clauses": [
        {"id": "clause_1", "span": {"start": 0, "end": 63}, "outcome_refs": ["outcome_1"]},
        {"id": "clause_2", "span": {"start": 65, "end": 88}, "outcome_refs": []},
    ],
    "outcomes": [
        {
            "id": "outcome_1",
            "goal_class": "search",
            "clause_ref": "clause_1",
            "source_evidence": [{"start": 0, "end": 4, "text": "Find"}],
        }
    ],
}

COVERAGE = {
    "outcomes": [
        {"id": "outcome_1", "status": "covered_by_goal", "goal_ids": ["g1"]}
    ],
    "summary": {"required": 1, "covered": 1, "missing": 0},
}

AGENT_TRACE = {
    "status": "injected",
    "skills": [
        {
            "id": "date-diff",
            "version": "1.0.0",
            "selected": True,
            "matched_triggers": ["year difference"],
            "instructions_sha256": "a" * 64,
            "source": "skill_registry",
            "registry_manifest_sha256": "b" * 64,
            "selection_policy": "declared_trigger_phrase_substring_v1",
        },
        {
            "id": "never-triggered",
            "version": "2.0.0",
            "selected": False,
            "matched_triggers": [],
            "instructions_sha256": "c" * 64,
            "selection_policy": "declared_trigger_phrase_substring_v1",
        },
    ],
}

GOAL_SPEC = {"goals": [{"id": "g1", "class": "search"}]}


def test_clause_outcome_goal_skill_chain_is_composed():
    trace = build_objective_skill_traceability(
        objective=OBJECTIVE,
        contract_v3=CONTRACT_V3,
        coverage=COVERAGE,
        agent_context_trace=AGENT_TRACE,
        goal_spec=GOAL_SPEC,
    )
    assert trace["schema"] == "taas.objective-skill-traceability/v1"
    assert trace["provenance_scope"].startswith("lexical")
    assert trace["semantic_correctness_verified"] is False
    assert trace["tools_authorized"] is False
    assert trace["execution_enabled"] is False

    outcome = trace["outcome_provenance"][0]
    assert outcome["clause_ref"] == "clause_1"
    assert outcome["covered_by_goal_ids"] == ["g1"]
    assert outcome["skills_triggered_in_clause"] == ["date-diff"]

    goal = trace["goal_provenance"][0]
    assert goal["goal_id"] == "g1"
    assert goal["linked_outcome_id"] == "outcome_1"
    assert goal["clause_ref"] == "clause_1"


def test_trigger_occurrences_carry_spans_and_clause_refs():
    trace = build_objective_skill_traceability(
        objective=OBJECTIVE,
        contract_v3=CONTRACT_V3,
        coverage=COVERAGE,
        agent_context_trace=AGENT_TRACE,
        goal_spec=GOAL_SPEC,
    )
    skill = trace["skill_selection"][0]
    trigger = skill["matched_triggers"][0]
    assert trigger["phrase"] == "year difference"
    occurrence = trigger["occurrences"][0]
    assert OBJECTIVE[occurrence["start"]:occurrence["end"]] == "year difference"
    assert occurrence["clause_ref"] == "clause_1"
    assert skill["registry_manifest_sha256"] == "b" * 64
    assert skill["source"] == "skill_registry"


def test_unselected_skill_has_no_occurrences_and_stays_auditable():
    trace = build_objective_skill_traceability(
        objective=OBJECTIVE,
        contract_v3=CONTRACT_V3,
        coverage=COVERAGE,
        agent_context_trace=AGENT_TRACE,
        goal_spec=GOAL_SPEC,
    )
    unselected = trace["skill_selection"][1]
    assert unselected["skill_id"] == "never-triggered"
    assert unselected["selected"] is False
    assert unselected["matched_triggers"] == []


def test_missing_context_produces_empty_but_honest_trace():
    trace = build_objective_skill_traceability(
        objective=OBJECTIVE,
        contract_v3=None,
        coverage=None,
        agent_context_trace=None,
        goal_spec=None,
    )
    assert trace["skill_selection"] == []
    assert trace["outcome_provenance"] == []
    assert trace["agent_context_status"] == "not_configured"
    assert trace["semantic_correctness_verified"] is False


def test_objective_prepare_response_includes_traceability_record(monkeypatch):
    class FakeRuntime:
        def decompose(self, prompt, context="", max_new_tokens=1200, agent_context=None):
            return {
                "text": "not-json",
                "json_valid": False,
                "parse_error": "candidate rejected",
                "goal_spec": None,
                "model_id": "org/model",
                "latency_seconds": 0.01,
            }

    monkeypatch.setattr(studio_api, "get_model_runtime", lambda: FakeRuntime())
    monkeypatch.setattr(studio_api, "prepare_agent_candidate", lambda r, p, c: r)
    monkeypatch.setattr(studio_api, "build_objective_context", lambda prompt: "")

    response = studio_api.agent_decompose(
        AgentDecomposeRequest(prompt="Find the year difference between two dates.")
    )
    trace = response["objective_skill_traceability"]
    assert trace["schema"] == "taas.objective-skill-traceability/v1"
    assert trace["agent_context_status"] == "not_configured"
    assert trace["semantic_correctness_verified"] is False
    assert trace["tools_authorized"] is False
