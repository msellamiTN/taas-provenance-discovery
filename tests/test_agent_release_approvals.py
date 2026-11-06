from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio import assurance_evidence
from taas.studio.release_readiness import (
    build_release_subject_binding,
    evaluate_release_readiness,
    evidence_store_lookup,
)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "release-approval-test-token")
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    monkeypatch.setenv("TAAS_EVIDENCE_DB_PATH", str(tmp_path / "evidence.sqlite3"))
    monkeypatch.setenv("TAAS_EVIDENCE_ATTESTATION_KEY", "x" * 40)
    monkeypatch.setenv("TAAS_STUDIO_ACTOR", "release-operator")
    return TestClient(studio_api.app)


def headers():
    return {"Authorization": "Bearer release-approval-test-token"}


def agent_manifest(agent_id="release-candidate"):
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Agent",
        "metadata": {"id": agent_id, "name": "Release candidate", "version": "1.0.0"},
        "spec": {
            "model": {"provider": "huggingface", "model_id": "Qwen/Qwen2.5-0.5B-Instruct"},
            "instructions": "Decompose objectives conservatively.",
            "tool_allowlist": [],
            "approval": {"require_assurance": True},
        },
    }


def _create_and_validate(client, manifest=None):
    body = manifest or agent_manifest()
    created = client.post("/api/v1/agents", json=body, headers=headers())
    assert created.status_code == 201, created.text
    agent_id = body["metadata"]["id"]
    version = body["metadata"]["version"]
    validated = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/validate", headers=headers()
    )
    assert validated.status_code == 200, validated.text
    return agent_id, version


def _readiness(client, agent_id, version):
    response = client.get(
        f"/api/v1/agents/{agent_id}/versions/{version}/release-readiness",
        headers=headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _agent_record(client, agent_id, version):
    response = client.get(
        f"/api/v1/agents/{agent_id}/versions/{version}", headers=headers()
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_approval_requires_validated_or_published_agent(client):
    body = agent_manifest()
    created = client.post("/api/v1/agents", json=body, headers=headers())
    assert created.status_code == 201
    response = client.post(
        f"/api/v1/agents/{body['metadata']['id']}/versions/1.0.0/approvals",
        json={}, headers=headers(),
    )
    assert response.status_code == 409


def test_approval_unknown_agent_is_404(client):
    response = client.post(
        "/api/v1/agents/ghost/versions/1.0.0/approvals", json={}, headers=headers()
    )
    assert response.status_code == 404


def test_approval_record_is_bound_attested_and_never_authorizing(client):
    agent_id, version = _create_and_validate(client)
    response = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={"note": "reviewed manifest, snapshot and certificate"},
        headers=headers(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["integrity_verified"] is True
    assert body["authorization_granted"] is False
    assert body["execution_enabled"] is False
    assert body["assessor_claim_truth_verified"] is False
    approval = body["approval"]
    assert approval["evidence_type"] == "human_approval"
    assert approval["assessor"] == "release-operator"
    binding = approval["subject_binding"]
    agent = _agent_record(client, agent_id, version)
    assert binding["manifest_sha256"] == agent["manifest_sha256"]
    assert binding["agent_id"] == agent_id

    listed = client.get(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals", headers=headers()
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["approvals"][0]["payload"]["decision"] == "approved"


def test_readiness_reaches_ready_only_with_both_evidence_records(client):
    agent_id, version = _create_and_validate(client)

    before = _readiness(client, agent_id, version)
    assert before["decision"] == "NEEDS_REVIEW"
    assert before["checks"]["trusted_assurance_evidence_verified"] is False
    assert before["checks"]["human_approval_record_verified"] is False
    assert before["authorization_granted"] is False
    assert before["execution_enabled"] is False

    approved = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={"note": "manual review complete"},
        headers=headers(),
    )
    assert approved.status_code == 201
    mid = _readiness(client, agent_id, version)
    assert mid["decision"] == "NEEDS_REVIEW"
    assert mid["checks"]["human_approval_record_verified"] is True
    assert mid["checks"]["trusted_assurance_evidence_verified"] is False

    agent = _agent_record(client, agent_id, version)
    binding = build_release_subject_binding(agent)
    envelope = assurance_evidence.attest_evidence(
        evidence_type="provenance_verification",
        subject_binding=binding,
        issuer="taas-studio",
        assessor="provenance-assessor-v1",
        method="registry-snapshot-provenance-review",
        payload={"scope": "release", "result": "verified"},
    )
    assurance_evidence.store_evidence(envelope)

    final = _readiness(client, agent_id, version)
    assert final["decision"] == "READY"
    assert final["checks"]["trusted_assurance_evidence_verified"] is True
    assert final["checks"]["human_approval_record_verified"] is True
    assert final["authorization_granted"] is False
    assert final["execution_enabled"] is False
    assert final["evidence"]["human_approval"]["available"] is True
    assert final["evidence"]["provenance_verification"]["available"] is True


def test_approval_bound_to_exact_manifest_does_not_cover_other_versions(client):
    agent_id, version = _create_and_validate(client)
    assert client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    ).status_code == 201

    agent = _agent_record(client, agent_id, version)
    other = dict(agent)
    other["version"] = "9.9.9"
    report = evaluate_release_readiness(
        agent=other, snapshot=None, evidence_lookup=evidence_store_lookup(other)
    )
    assert report["checks"]["human_approval_record_verified"] is False
    assert report["decision"] != "READY"


def test_expired_approval_does_not_satisfy_gate(client, monkeypatch):
    agent_id, version = _create_and_validate(client)
    agent = _agent_record(client, agent_id, version)
    binding = build_release_subject_binding(agent)
    stale = datetime.now(timezone.utc) - timedelta(hours=2)
    envelope = assurance_evidence.attest_evidence(
        evidence_type="human_approval",
        subject_binding=binding,
        issuer="taas-studio",
        assessor="release-operator",
        method="studio_operator_approval",
        payload={"decision": "approved", "note": "stale"},
        ttl_seconds=60,
        observed_at=stale,
    )
    assurance_evidence.store_evidence(envelope)

    report = evaluate_release_readiness(
        agent=agent, snapshot=None, evidence_lookup=evidence_store_lookup(agent)
    )
    assert report["checks"]["human_approval_record_verified"] is False
    assert report["evidence"]["human_approval"]["available"] is False


def test_human_approval_does_not_impersonate_assurance_evidence(client):
    agent_id, version = _create_and_validate(client)
    assert client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    ).status_code == 201
    report = _readiness(client, agent_id, version)
    assert report["checks"]["human_approval_record_verified"] is True
    assert report["checks"]["trusted_assurance_evidence_verified"] is False


def test_approval_endpoint_fails_closed_without_attestation_key(client, monkeypatch):
    agent_id, version = _create_and_validate(client)
    monkeypatch.delenv("TAAS_EVIDENCE_ATTESTATION_KEY")
    response = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    )
    assert response.status_code == 503
    assert "ATTESTATION_KEY" in response.json()["detail"]

    report = _readiness(client, agent_id, version)
    assert report["decision"] == "NEEDS_REVIEW"
    assert report["checks"]["human_approval_record_verified"] is False


def test_approval_payload_rejects_extra_fields(client):
    agent_id, version = _create_and_validate(client)
    response = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={"note": "ok", "approve_execution": True},
        headers=headers(),
    )
    assert response.status_code == 422


def test_approval_replay_by_same_assessor_is_409(client, monkeypatch):
    monkeypatch.setenv("TAAS_AUDIT_LEDGER_PATH",
                       str(__import__("pathlib").Path.cwd() / "audit-test.sqlite3"))
    agent_id, version = _create_and_validate(client)
    first = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    )
    assert first.status_code == 201
    replay = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    )
    assert replay.status_code == 409
    assert "already exists" in replay.json()["detail"]


def test_approval_by_distinct_assessor_is_allowed(client, monkeypatch):
    agent_id, version = _create_and_validate(client)
    first = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    )
    assert first.status_code == 201
    monkeypatch.setenv("TAAS_STUDIO_ACTOR", "second-operator")
    second = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    )
    assert second.status_code == 201
    assert second.json()["approval"]["assessor"] == "second-operator"


def test_approval_event_lands_in_audit_ledger(client, monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_AUDIT_LEDGER_PATH", str(tmp_path / "audit.sqlite3"))
    from taas.studio import audit_ledger
    agent_id, version = _create_and_validate(client)
    created = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    )
    assert created.status_code == 201
    events = audit_ledger.list_events(event_type="approval")
    assert len(events) == 1
    assert events[0]["subject"]["agent_id"] == agent_id
    assert events[0]["payload"]["assessor"] == "release-operator"
    assert audit_ledger.verify_chain()["chain_valid"] is True


def test_approval_renewal_blocked_while_prior_record_fresh_and_expiry_verified(client):
    agent_id, version = _create_and_validate(client)
    short = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={"ttl_seconds": 300}, headers=headers(),
    )
    assert short.status_code == 201
    # While the first approval is still fresh, a same-assessor replay is a 409.
    renewed = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/approvals",
        json={}, headers=headers(),
    )
    assert renewed.status_code == 409
    # After the TTL horizon the stored record is no longer verified-fresh —
    # expiry is enforced by the evidence layer, so renewal becomes legal then.
    from datetime import datetime, timedelta, timezone
    from taas.studio import assurance_evidence, release_readiness
    future = datetime.now(timezone.utc) + timedelta(seconds=400)
    listing = assurance_evidence.list_verified_evidence_for_subject(
        release_readiness.build_release_subject_binding(
            _agent_record(client, agent_id, version)),
        expected_type="human_approval", now=future)
    assert listing["count"] == 0
