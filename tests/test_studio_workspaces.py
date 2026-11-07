"""Durable workspace draft persistence — Phase 4 of the Studio megaplan."""
import pytest
from fastapi.testclient import TestClient

from taas.studio.api import app

client = TestClient(app)
HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def _workspace_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("TAAS_WORKSPACES_PATH", str(tmp_path / "workspaces.sqlite3"))


def _create(name="draft-1"):
    return client.post(
        "/api/v1/workspaces",
        json={"name": name, "draft": {"goal_spec": {"prompt": "x"}, "tools": []}},
        headers=HEADERS,
    )


def test_workspaces_require_authentication():
    response = client.get("/api/v1/workspaces", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401


def test_create_get_and_delete_round_trip():
    created = _create()
    assert created.status_code == 201
    record = created.json()
    assert record["schema"] == "taas.workspace-draft/v1"
    assert record["record_semantics"] == "authored_draft_not_analysis_not_execution"
    assert record["revision"] == 1

    fetched = client.get(f"/api/v1/workspaces/{record['workspace_id']}", headers=HEADERS)
    assert fetched.status_code == 200
    assert fetched.json()["draft"]["goal_spec"]["prompt"] == "x"

    deleted = client.delete(f"/api/v1/workspaces/{record['workspace_id']}", headers=HEADERS)
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/workspaces/{record['workspace_id']}", headers=HEADERS).status_code == 404


def test_update_rejects_stale_revision_with_409():
    workspace_id = _create().json()["workspace_id"]
    ok = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"draft": {"goal_spec": {"prompt": "y"}}, "revision": 1},
        headers=HEADERS,
    )
    assert ok.status_code == 200
    assert ok.json()["revision"] == 2

    stale = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"draft": {"goal_spec": {"prompt": "z"}}, "revision": 1},
        headers=HEADERS,
    )
    assert stale.status_code == 409
    # The stale write must not have clobbered the draft.
    assert client.get(
        f"/api/v1/workspaces/{workspace_id}", headers=HEADERS
    ).json()["draft"]["goal_spec"]["prompt"] == "y"


def test_list_returns_metadata_only_and_is_bounded():
    _create("a")
    _create("b")
    listing = client.get("/api/v1/workspaces?limit=1", headers=HEADERS)
    assert listing.status_code == 200
    body = listing.json()
    assert body["schema"] == "taas.workspace-list/v1"
    assert body["count"] == 1
    assert "draft" not in body["workspaces"][0]


def test_unknown_workspace_fails_closed():
    assert client.get("/api/v1/workspaces/nope", headers=HEADERS).status_code == 404
    assert client.delete("/api/v1/workspaces/nope", headers=HEADERS).status_code == 404
    assert client.put(
        "/api/v1/workspaces/nope",
        json={"draft": {}, "revision": 1},
        headers=HEADERS,
    ).status_code == 404


def test_reference_vocabulary_declared_only():
    response = client.get("/api/v1/reference/vocabulary", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "taas.vocabulary/v1"
    assert body["vocabulary_semantics"] == "declared_authoring_reference_not_verified_evidence"
    assert body["theta"]["kinds"] and body["theta"]["domains"]
    assert body["goal_classes"]["external"] and body["sigma_values"]


def test_request_id_echoed_or_assigned():
    response = client.get("/health")
    assert response.headers.get("x-request-id")
    echoed = client.get("/health", headers={"X-Request-ID": "req-42"})
    assert echoed.headers["x-request-id"] == "req-42"


def test_goal_spec_validation_response_carries_schema():
    response = client.post(
        "/api/v1/goals/validate",
        headers=HEADERS,
        json={
            "prompt": "Retrieve orders",
            "prompt_inputs": ["text"],
            "goals": [
                {"id": "g1", "class": "retrieve", "in": [], "out": "record[]",
                 "eff": ["read(*)"], "sigma": "data", "deps": [], "desc": "Retrieve orders"}
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["schema"] == "taas.goal-spec-validation/v1"
