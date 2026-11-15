"""S1 — named API keys: per-key actor identity, hashed storage, revocation.

Keys are authentication credentials only. These tests prove identity
binding (a key's writes carry its declared actor) and fail-closed
behaviour (revoked/unknown/missing credentials never authenticate), and
that key lifecycle events land in the hash-chained audit ledger.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio import api_keys, audit_ledger

SHARED = "shared-bootstrap-token"
HEADERS = {"Authorization": f"Bearer {SHARED}"}


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_API_KEYS_PATH", str(tmp_path / "keys.sqlite3"))
    monkeypatch.setenv("TAAS_AUDIT_LEDGER_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("TAAS_WORKSPACES_PATH", str(tmp_path / "workspaces.sqlite3"))
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", SHARED)
    monkeypatch.delenv("TAAS_STUDIO_ACTOR", raising=False)
    yield


@pytest.fixture()
def client():
    return TestClient(studio_api.app)


def _create_key(client, name="ci-bot", actor="ci-bot-actor"):
    resp = client.post("/api/v1/admin/api-keys", headers=HEADERS,
                       json={"name": name, "actor": actor})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_returns_token_once_and_metadata_only(client):
    body = _create_key(client)
    assert body["schema"] == "taas.api-key/v1"
    assert body["token"].startswith("taas_")
    assert body["token_displayed_once"] is True
    assert body["plaintext_persisted"] is False
    assert body["authentication_credential"] is True
    assert body["authorization_granted"] is False
    assert body["execution_enabled"] is False
    assert body["state"] == "active"

    listing = client.get("/api/v1/admin/api-keys", headers=HEADERS).json()
    assert listing["schema"] == "taas.api-key-list/v1"
    assert listing["active_count"] == 1
    entry = listing["keys"][0]
    assert entry["key_id"] == body["key_id"]
    assert entry["actor"] == "ci-bot-actor"
    for forbidden in ("token", "key_hash", "key_hash "):
        assert forbidden not in entry
    assert "credential_semantics" in listing


def test_named_key_binds_actor_identity_on_writes(client):
    key = _create_key(client, actor="release-engineer")
    headers = {"Authorization": f"Bearer {key['token']}"}

    created = client.post("/api/v1/workspaces", headers=headers, json={
        "name": "key-actor-ws", "draft": {"goal": "g"}})
    assert created.status_code == 201, created.text
    ws_id = created.json()["workspace_id"]

    history = client.get(
        f"/api/v1/workspaces/{ws_id}/revisions", headers=headers).json()
    assert history["revisions"][0]["actor"] == "release-engineer"


def test_shared_token_still_authenticates_with_env_actor(client, monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_ACTOR", "shared-op")
    created = client.post("/api/v1/workspaces", headers=HEADERS, json={
        "name": "shared-ws", "draft": {"goal": "g"}})
    assert created.status_code == 201, created.text
    ws_id = created.json()["workspace_id"]
    history = client.get(
        f"/api/v1/workspaces/{ws_id}/revisions", headers=HEADERS).json()
    assert history["revisions"][0]["actor"] == "shared-op"


def test_revoked_key_returns_401(client):
    key = _create_key(client)
    headers = {"Authorization": f"Bearer {key['token']}"}
    assert client.get("/api/v1/workspaces", headers=headers).status_code == 200

    revoked = client.post(
        f"/api/v1/admin/api-keys/{key['key_id']}/revoke", headers=HEADERS)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["state"] == "revoked"
    assert revoked.json()["revoked_by"] == "shared-op" or \
        revoked.json()["revoked_by"] == "studio-api"

    assert client.get("/api/v1/workspaces", headers=headers).status_code == 401


def test_revoke_unknown_404_and_double_revoke_409(client):
    assert client.post("/api/v1/admin/api-keys/ak_" + "0" * 16 + "/revoke",
                       headers=HEADERS).status_code == 404
    key = _create_key(client)
    url = f"/api/v1/admin/api-keys/{key['key_id']}/revoke"
    assert client.post(url, headers=HEADERS).status_code == 200
    assert client.post(url, headers=HEADERS).status_code == 409


def test_admin_routes_require_auth(client):
    assert client.get("/api/v1/admin/api-keys").status_code == 401
    assert client.post("/api/v1/admin/api-keys",
                       json={"name": "x", "actor": "y"}).status_code == 401
    bad = client.get("/api/v1/admin/api-keys",
                     headers={"Authorization": "Bearer wrong"})
    assert bad.status_code == 401


def test_key_lifecycle_lands_in_audit_ledger(client):
    key = _create_key(client, name="audited", actor="auditor")
    client.post(f"/api/v1/admin/api-keys/{key['key_id']}/revoke", headers=HEADERS)
    events = audit_ledger.list_events(event_type="api_key", limit=10)
    actions = [e["payload"].get("action") for e in events]
    assert "created" in actions and "revoked" in actions
    assert audit_ledger.verify_chain()["chain_valid"] is True


def test_named_key_survives_shared_token_removal(client, monkeypatch):
    """Once a named key exists, the shared bootstrap token can be retired:
    the key still authenticates and wrong tokens still fail closed."""
    key = _create_key(client)
    headers = {"Authorization": f"Bearer {key['token']}"}
    monkeypatch.delenv("TAAS_STUDIO_API_TOKEN")
    assert client.get("/api/v1/workspaces", headers=headers).status_code == 200
    assert client.get("/api/v1/workspaces", headers=HEADERS).status_code == 401


def test_503_when_no_credential_source_configured(client, monkeypatch):
    """No shared token and an empty keystore → 503, matching prior behavior."""
    monkeypatch.delenv("TAAS_STUDIO_API_TOKEN")
    resp = client.get("/api/v1/workspaces", headers=HEADERS)
    assert resp.status_code == 503
