from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "skill-registry-test-token")
    monkeypatch.setenv("TAAS_SKILL_REGISTRY_PATH", str(tmp_path / "skills.sqlite3"))
    monkeypatch.setenv("TAAS_STUDIO_ACTOR", "api-test")
    return TestClient(studio_api.app)


def headers():
    return {"Authorization": "Bearer skill-registry-test-token"}


def payload():
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Skill",
        "metadata": {
            "id": "date-arithmetic",
            "name": "Date arithmetic",
            "version": "1.0.0",
            "description": "Reusable date calculation guidance",
        },
        "spec": {
            "instructions": "Acquire each date independently, then compute the exact difference.",
            "trigger_phrases": ["date difference", "year difference"],
            "tags": ["calculation"],
        },
    }


def test_skill_api_validate_is_non_persistent_and_non_authorizing(client):
    response = client.post("/api/v1/skills/validate", json=payload(), headers=headers())
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["lifecycle_state"] == "draft"
    assert body["tools_authorized"] is False
    assert body["execution_enabled"] is False
    assert client.get("/api/v1/skills", headers=headers()).json()["count"] == 0


def test_skill_api_create_get_and_duplicate_conflict(client):
    created = client.post("/api/v1/skills", json=payload(), headers=headers())
    assert created.status_code == 201
    assert created.json()["lifecycle_state"] == "draft"
    assert created.json()["tools_authorized"] is False
    assert client.post("/api/v1/skills", json=payload(), headers=headers()).status_code == 409
    fetched = client.get("/api/v1/skills/date-arithmetic/versions/1.0.0", headers=headers())
    assert fetched.status_code == 200
    assert fetched.json()["manifest"]["metadata"]["id"] == "date-arithmetic"


def test_skill_api_lifecycle_requires_validation_and_is_audited(client):
    assert client.post("/api/v1/skills", json=payload(), headers=headers()).status_code == 201
    premature = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/publish", headers=headers()
    )
    assert premature.status_code == 409
    validated = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/validate", headers=headers()
    )
    assert validated.status_code == 200
    assert validated.json()["validation_scope"] == "structural_schema_and_field_invariants"
    published = client.post(
        "/api/v1/skills/date-arithmetic/versions/1.0.0/publish", headers=headers()
    )
    assert published.status_code == 200
    assert published.json()["lifecycle_state"] == "published"
    assert published.json()["published_as_guidance"] is True
    assert published.json()["tools_authorized"] is False
    events = client.get("/api/v1/skills/events?skill_id=date-arithmetic", headers=headers()).json()
    assert events["count"] == 3
    assert {event["actor"] for event in events["events"]} == {"api-test"}


def test_skill_api_rejects_unknown_fields_and_requires_auth(client):
    invalid = payload()
    invalid["spec"]["grants_tools"] = True
    assert client.post("/api/v1/skills/validate", json=invalid, headers=headers()).status_code == 422
    assert client.get("/api/v1/skills").status_code == 401


def test_skill_api_missing_version_returns_not_found(client):
    response = client.get("/api/v1/skills/no-such-skill/versions/1.0.0", headers=headers())
    assert response.status_code == 404
