from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "skill-trust-test-token")
    monkeypatch.setenv("TAAS_SKILL_REGISTRY_PATH", str(tmp_path / "skills.sqlite3"))
    monkeypatch.setenv("TAAS_EVIDENCE_DB_PATH", str(tmp_path / "evidence.sqlite3"))
    monkeypatch.setenv("TAAS_EVIDENCE_ATTESTATION_KEY", "y" * 40)
    monkeypatch.setenv("TAAS_STUDIO_ACTOR", "registry-operator")
    return TestClient(studio_api.app)


def headers():
    return {"Authorization": "Bearer skill-trust-test-token"}


def payload(skill_id="date-arithmetic", version="1.0.0"):
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Skill",
        "metadata": {
            "id": skill_id,
            "name": "Date arithmetic",
            "version": version,
            "description": "Reusable date calculation guidance",
        },
        "spec": {
            "instructions": "Acquire each date independently, then compute the exact difference.",
            "trigger_phrases": ["date difference"],
            "tags": ["calculation"],
        },
    }


def _publish(client, skill_id="date-arithmetic", version="1.0.0"):
    body = payload(skill_id, version)
    assert client.post("/api/v1/skills", json=body, headers=headers()).status_code == 201
    assert client.post(
        f"/api/v1/skills/{skill_id}/versions/{version}/validate", headers=headers()
    ).status_code == 200
    assert client.post(
        f"/api/v1/skills/{skill_id}/versions/{version}/publish", headers=headers()
    ).status_code == 200


def test_sign_published_skill_and_verify_signature(client):
    _publish(client)
    signed = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/sign",
        json={"publisher_id": "org:taas-labs", "statement": "reviewed for reuse"},
        headers=headers(),
    )
    assert signed.status_code == 201, signed.text
    body = signed.json()
    assert body["integrity_verified"] is True
    assert body["signature_scope"] == "registry_attested_not_portable_identity"
    assert body["signature"]["publisher_id"] == "org:taas-labs"
    assert body["signature"]["subject_binding"]["skill_id"] == "date-arithmetic"
    assert body["tools_authorized"] is False
    assert body["assessor_claim_truth_verified"] is False

    status = client.get(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/signature", headers=headers()
    )
    assert status.status_code == 200
    report = status.json()
    assert report["verified"] is True
    assert report["signatures"][0]["publisher_id"] == "org:taas-labs"
    assert report["signatures"][0]["signed_by"] == "registry-operator"


def test_unsigned_skill_reports_unverified_signature(client):
    _publish(client)
    status = client.get(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/signature", headers=headers()
    )
    assert status.status_code == 200
    assert status.json()["verified"] is False
    assert status.json()["signatures"] == []


def test_sign_requires_published_skill(client):
    assert client.post("/api/v1/skills", json=payload(), headers=headers()).status_code == 201
    response = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/sign", json={}, headers=headers()
    )
    assert response.status_code == 409


def test_sign_fails_closed_without_attestation_key(client, monkeypatch):
    _publish(client)
    monkeypatch.delenv("TAAS_EVIDENCE_ATTESTATION_KEY")
    response = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/sign", json={}, headers=headers()
    )
    assert response.status_code == 503
    assert "ATTESTATION_KEY" in response.json()["detail"]


def test_signature_is_bound_to_exact_manifest_digest(client):
    _publish(client)
    assert client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/sign", json={}, headers=headers()
    ).status_code == 201

    _publish(client, skill_id="date-arithmetic", version="2.0.0")
    status = client.get(
        "/api/v1/skills/date-arithmetic/versions/2.0.0/signature", headers=headers()
    )
    assert status.json()["verified"] is False


def test_revoked_skill_refuses_new_signatures_and_bindings(client):
    _publish(client)
    revoked = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/revoke",
        json={"reason": "dependency contains unsafe guidance"},
        headers=headers(),
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked"] is True
    assert revoked.json()["revocation"]["reason"] == "dependency contains unsafe guidance"

    signed = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/sign", json={}, headers=headers()
    )
    assert signed.status_code == 409

    resource = client.get(
        "/api/v1/skills/date-arithmetic/versions/1.0.0", headers=headers()
    )
    assert resource.json()["revoked"] is True

    listed = client.get("/api/v1/skills", headers=headers()).json()
    assert listed["versions"][0]["revoked"] is True

    dependency = client.get(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/dependency-graph",
        headers=headers(),
    )
    assert dependency.status_code == 200
    assert dependency.json()["nodes"][0]["revoked"] is True

    status = client.get(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/revocation", headers=headers()
    )
    assert status.status_code == 200
    assert status.json()["revoked"] is True
    assert status.json()["revocation"]["revoked_by"] == "registry-operator"


def test_revocation_is_immutable_and_requires_reason(client):
    _publish(client)
    first = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/revoke",
        json={"reason": "superseded"}, headers=headers(),
    )
    assert first.status_code == 200
    again = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/revoke",
        json={"reason": "twice"}, headers=headers(),
    )
    assert again.status_code == 409

    _publish(client, skill_id="empty-reason")
    assert client.post(
        "/api/v1/skills/empty-reason/versions/1.0.0/revoke",
        json={"reason": "   "}, headers=headers(),
    ).status_code == 422


def test_draft_skill_cannot_be_revoked_and_unknown_is_404(client):
    assert client.post("/api/v1/skills", json=payload(), headers=headers()).status_code == 201
    assert client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/revoke",
        json={"reason": "draft"}, headers=headers(),
    ).status_code == 409
    assert client.post(
        "/api/v1/skills/ghost/versions/1.0.0/revoke",
        json={"reason": "none"}, headers=headers(),
    ).status_code == 404


def test_revoked_skill_is_refused_for_agent_binding(client):
    _publish(client)
    resource = client.get(
        "/api/v1/skills/date-arithmetic/versions/1.0.0", headers=headers()
    ).json()
    assert client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/revoke",
        json={"reason": "supply-chain incident"}, headers=headers(),
    ).status_code == 200

    from taas.studio.agent_skill_bindings import (
        AgentSkillBindingConflict, resolve_agent_skill_references,
    )

    manifest = {
        "spec": {
            "skill_refs": [{
                "id": "date-arithmetic",
                "version": "1.0.0",
                "manifest_sha256": resource["manifest_sha256"],
            }],
        },
    }
    with pytest.raises(AgentSkillBindingConflict, match="revoked"):
        resolve_agent_skill_references(manifest)
