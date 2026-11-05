from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio.policy_engine import evaluate_policy


READY_FACTS = {
    "release_readiness": {"decision": "READY"},
    "evidence_summary": {"verified_records": 2, "invalid_records": 0},
    "skill_trust": {
        "skills": [
            {
                "skill_id": "date-diff", "version": "1.0.0", "resolution": "resolved",
                "revoked": False, "signature_required": False, "signature_verified": True,
            }
        ],
        "signature_required": False,
    },
    "authorization_preflight": {"authorized": True},
    "objective_contract_valid": True,
}

SUBJECT = {"kind": "objective_candidate", "objective_sha256": "a" * 64}
AGENT_SUBJECT = {"kind": "agent_version", "agent_id": "a", "version": "1.0.0",
                 "manifest_sha256": "b" * 64}


def test_allow_only_when_all_applicable_rules_pass():
    verdict = evaluate_policy(AGENT_SUBJECT, READY_FACTS)
    assert verdict["schema"] == "taas.policy-verdict/v1"
    assert verdict["decision"] == "allow"
    assert verdict["execution_enabled"] is False
    assert verdict["authorization_granted"] is False
    assert all(f["outcome"] in ("pass", "not_applicable") for f in verdict["fired_rules"])


def test_revoked_skill_denies_even_when_gate_ready():
    facts = dict(READY_FACTS)
    facts["skill_trust"] = {
        "skills": [{"skill_id": "evil", "version": "9.9.9", "resolution": "resolved",
                    "revoked": True, "signature_required": False}],
        "signature_required": False,
    }
    verdict = evaluate_policy(AGENT_SUBJECT, facts)
    assert verdict["decision"] == "deny"
    assert "skills_resolvable_not_revoked" in verdict["blocking_failures"]
    conflict = verdict["conflicts"][0]
    assert conflict["kind"] == "readiness_vs_trust_conflict"
    assert conflict["resolution"] == "deny_takes_precedence"


def test_missing_facts_needs_review_never_allow():
    verdict = evaluate_policy(AGENT_SUBJECT, {})
    assert verdict["decision"] == "needs_review"
    unknowns = {f["rule_id"] for f in verdict["fired_rules"] if f["outcome"] == "unknown"}
    assert "release_gate_ready" in unknowns
    assert "skills_resolvable_not_revoked" in unknowns


def test_needs_review_when_gate_not_ready():
    facts = dict(READY_FACTS)
    facts["release_readiness"] = {"decision": "NEEDS_REVIEW"}
    verdict = evaluate_policy(AGENT_SUBJECT, facts)
    assert verdict["decision"] == "needs_review"
    assert "release_gate_ready" in verdict["review_findings"]


def test_evidence_invalid_records_need_review():
    facts = dict(READY_FACTS)
    facts["evidence_summary"] = {"verified_records": 1, "invalid_records": 3}
    assert evaluate_policy(AGENT_SUBJECT, facts)["decision"] == "needs_review"


def test_subject_scoping_marks_rules_not_applicable():
    verdict = evaluate_policy(AGENT_SUBJECT, READY_FACTS)
    na = {f["rule_id"] for f in verdict["fired_rules"] if f["outcome"] == "not_applicable"}
    assert "structural_contract_valid" in na
    # full-scope subject still runs the contract rule
    full = evaluate_policy(SUBJECT, READY_FACTS)
    assert not any(f["outcome"] == "not_applicable" for f in full["fired_rules"])


def test_invalid_subject_rejected():
    with pytest.raises(ValueError, match="requires a kind"):
        evaluate_policy({}, READY_FACTS)


def test_signature_enforcement_via_required_flag():
    facts = dict(READY_FACTS)
    facts["skill_trust"] = {
        "skills": [{"skill_id": "s", "version": "1", "resolution": "resolved",
                    "revoked": False, "signature_required": True, "signature_verified": False}],
        "signature_required": True,
    }
    assert evaluate_policy(AGENT_SUBJECT, facts)["decision"] == "deny"


def test_deterministic_verdict():
    a, b = evaluate_policy(AGENT_SUBJECT, READY_FACTS), evaluate_policy(AGENT_SUBJECT, READY_FACTS)
    assert a == b


def test_policy_evaluate_endpoint(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "policy-token")
    client = TestClient(studio_api.app)
    ok = client.post("/api/v1/policy/evaluate",
                     json={"subject": AGENT_SUBJECT, "facts": READY_FACTS},
                     headers={"Authorization": "Bearer policy-token"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["decision"] == "allow"
    assert body["facts_source"] == "caller_asserted"
    assert body["execution_enabled"] is False

    bad = client.post("/api/v1/policy/evaluate",
                      json={"subject": {"no_kind": True}},
                      headers={"Authorization": "Bearer policy-token"})
    assert bad.status_code == 422
    extra = client.post("/api/v1/policy/evaluate",
                        json={"subject": AGENT_SUBJECT, "rogue": 1},
                        headers={"Authorization": "Bearer policy-token"})
    assert extra.status_code == 422


def test_agent_policy_verdict_gathers_registry_facts(monkeypatch):
    agent = {
        "agent_id": "research-assistant", "version": "1.2.0",
        "manifest": {"metadata": {"id": "research-assistant", "version": "1.2.0"},
                     "spec": {"description": "x", "objectives": ["o"], "skills": [],
                              "permissions": {"effects": [], "tool_classes": []}}},
        "manifest_sha256": "c" * 64, "lifecycle_state": "published",
        "registry_snapshot_id": None,
    }
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "policy-token")
    monkeypatch.setattr(studio_api.agent_registry, "get_version", lambda i, v: agent)
    monkeypatch.setattr(studio_api, "resolve_agent_skill_references", lambda m: (m, []))
    monkeypatch.setattr(studio_api.release_readiness, "evaluate_release_readiness",
                        lambda **kw: {"decision": "NEEDS_REVIEW"})
    monkeypatch.setattr(studio_api.assurance_evidence, "list_verified_evidence_for_subject",
                        lambda b, **kw: {"valid": [], "invalid": [], "count": 0})

    client = TestClient(studio_api.app)
    response = client.get("/api/v1/agents/research-assistant/versions/1.2.0/policy-verdict",
                          headers={"Authorization": "Bearer policy-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["facts_source"] == "registry_assembled"
    assert body["decision"] == "needs_review"
    assert body["release_readiness"]["decision"] == "NEEDS_REVIEW"
    assert body["execution_enabled"] is False
