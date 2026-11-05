from __future__ import annotations

import pytest

from taas.hypergraph_projection import project_objective_skill_traceability


TRACE = {
    "schema": "taas.objective-skill-traceability/v1",
    "objective_sha256": "d" * 64,
    "agent_context_status": "injected",
    "coverage_summary": {"required": 1, "covered": 1, "missing": 0},
    "clauses": [
        {"clause_id": "clause_1", "span": {"start": 0, "end": 63}, "outcome_refs": ["outcome_1"]},
    ],
    "outcome_provenance": [
        {
            "outcome_id": "outcome_1",
            "goal_class": "search",
            "clause_ref": "clause_1",
            "source_evidence": [{"start": 0, "end": 4, "text": "Find"}],
            "coverage_status": "covered_by_goal",
            "covered_by_goal_ids": ["g1"],
            "skills_triggered_in_clause": ["date-diff"],
        }
    ],
    "skill_selection": [
        {
            "skill_id": "date-diff",
            "version": "1.0.0",
            "selected": True,
            "source": "skill_registry",
            "instructions_sha256": "a" * 64,
            "registry_manifest_sha256": "b" * 64,
            "selection_policy": "declared_trigger_phrase_substring_v1",
            "matched_triggers": [
                {
                    "phrase": "year difference",
                    "occurrences": [{"start": 9, "end": 24, "clause_ref": "clause_1"}],
                }
            ],
        }
    ],
    "goal_provenance": [
        {
            "goal_id": "g1",
            "goal_class": "search",
            "linked_outcome_id": "outcome_1",
            "clause_ref": "clause_1",
            "skills_triggered_in_clause": ["date-diff"],
        }
    ],
    "provenance_scope": "lexical_trigger_and_clause_binding_only_not_semantic_proof",
    "semantic_correctness_verified": False,
    "tools_authorized": False,
    "execution_enabled": False,
}


def test_projection_builds_clause_outcome_goal_skill_vertices_and_relations():
    projection = project_objective_skill_traceability(TRACE)
    assert projection["schema"] == "taas.hypergraph-projection/v1"
    assert projection["projection_domain"] == "objective_skill_traceability"
    assert projection["graph_metadata"]["tools_authorized"] is False
    assert projection["graph_metadata"]["execution_enabled"] is False
    assert projection["graph_metadata"]["semantic_correctness_verified"] is False

    vertices = {v["id"]: v for v in projection["vertices"]}
    assert "clause:clause_1" in vertices
    assert "outcome:outcome_1" in vertices
    assert "goal:g1" in vertices
    assert "skill:date-diff@1.0.0" in vertices
    assert vertices["skill:date-diff@1.0.0"]["registry_manifest_sha256"] == "b" * 64
    assert vertices["clause:clause_1"]["span"] == {"start": 0, "end": 63}

    relations = {(e["relation"], e["source_vertex"], e["target_vertex"]) for e in projection["hyperedges"]}
    assert ("derives_outcome", "clause:clause_1", "outcome:outcome_1") in relations
    assert ("covered_by", "outcome:outcome_1", "goal:g1") in relations
    assert ("triggered_in", "skill:date-diff@1.0.0", "clause:clause_1") in relations
    for edge in projection["hyperedges"]:
        assert edge["authorization_effect"] == "none"
        assert edge["execution_effect"] == "none"


def test_trigger_edge_preserves_phrase_and_occurrence_span():
    projection = project_objective_skill_traceability(TRACE)
    trigger_edge = next(e for e in projection["hyperedges"] if e["kind"] == "skill_trigger_match")
    assert trigger_edge["trigger_phrase"] == "year difference"
    assert trigger_edge["occurrence_span"] == {"start": 9, "end": 24}
    assert trigger_edge["match_kind"] == "lexical_substring_not_semantic_proof"


def test_projection_is_deterministic():
    assert project_objective_skill_traceability(TRACE)["projection_id"] == \
        project_objective_skill_traceability(TRACE)["projection_id"]


def test_wrong_schema_rejected():
    with pytest.raises(ValueError, match="invalid objective_skill_traceability"):
        project_objective_skill_traceability({"schema": "taas.other/v1"})


def test_missing_clause_ref_edges_are_skipped_not_invented():
    trace = dict(TRACE)
    trace["outcome_provenance"] = [
        {**TRACE["outcome_provenance"][0], "clause_ref": "clause_ghost"}
    ]
    projection = project_objective_skill_traceability(trace)
    assert not any(e["relation"] == "derives_outcome" for e in projection["hyperedges"])
    assert any(v["id"] == "outcome:outcome_1" for v in projection["vertices"])


def test_bounds_enforced():
    trace = dict(TRACE)
    trace["skill_selection"] = [
        {"skill_id": f"s{i}", "version": "1.0.0", "matched_triggers": []}
        for i in range(33)
    ]
    with pytest.raises(ValueError, match="exceeds projection bounds"):
        project_objective_skill_traceability(trace)


def test_api_endpoint_projects_supplied_trace(monkeypatch):
    from fastapi.testclient import TestClient
    import taas.studio.api as studio_api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "trace-token")
    client = TestClient(studio_api.app)
    response = client.post(
        "/api/v1/hypergraph/objective-traceability",
        json={"traceability": TRACE},
        headers={"Authorization": "Bearer trace-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hypergraph_projection"]["projection_domain"] == "objective_skill_traceability"
    assert body["execution_enabled"] is False

    bad = client.post(
        "/api/v1/hypergraph/objective-traceability",
        json={"traceability": {"schema": "bogus"}},
        headers={"Authorization": "Bearer trace-token"},
    )
    assert bad.status_code == 422
