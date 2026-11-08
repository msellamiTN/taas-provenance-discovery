"""Parity/API-completeness tests filed by the lifecycle megaplan UX audit.

Covers version filtering on lifecycle events, subject filtering on audit
events, skill version diff + recorded activity, and MCP snapshot diff.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio import agent_registry, audit_ledger, skill_registry
from taas.studio.skill_spec import validate_skill_manifest


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "parity-token")
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    monkeypatch.setenv("TAAS_SKILL_REGISTRY_PATH", str(tmp_path / "skills.sqlite3"))
    monkeypatch.setenv("TAAS_AUDIT_LEDGER_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("TAAS_EVIDENCE_DB_PATH", str(tmp_path / "evidence.sqlite3"))
    monkeypatch.setenv("TAAS_EVIDENCE_ATTESTATION_KEY", "k" * 40)
    yield TestClient(studio_api.app)


HEADERS = {"Authorization": "Bearer parity-token"}


def _skill(skill_id: str, version: str, instructions: str = "do things"):
    return validate_skill_manifest({
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Skill",
        "metadata": {"id": skill_id, "name": skill_id, "version": version},
        "spec": {"instructions": instructions, "trigger_phrases": ["go"],
                 "tags": ["t"]},
    })


def test_skill_events_version_filter(client):
    skill_registry.create_draft(_skill("skill-one", "1.0.0"))
    skill_registry.create_draft(_skill("skill-one", "2.0.0"))
    response = client.get(
        "/api/v1/skills/events?skill_id=skill-one&version=1.0.0", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert all(e["version"] == "1.0.0" for e in body["events"])


def test_agent_events_version_filter(client):
    from taas.studio.agent_spec import validate_agent_manifest

    def _agent(v, instructions):
        return validate_agent_manifest({
            "apiVersion": "taas.ai/v1alpha1", "kind": "Agent",
            "metadata": {"id": "agent-one", "name": "agent-one", "version": v},
            "spec": {
                "model": {"provider": "huggingface", "model_id": "m/model"},
                "instructions": instructions,
                "tool_allowlist": [],
                "resources": {"max_new_tokens": 64, "timeout_seconds": 30,
                              "max_tool_calls": 0},
                "approval": {"require_human_approval": True,
                             "require_assurance": False,
                             "allow_side_effects": False},
            },
        })

    agent_registry.create_draft(_agent("1.0.0", "v1 instructions"))
    agent_registry.create_draft(_agent("2.0.0", "v2 instructions"))
    response = client.get(
        "/api/v1/agents/events?agent_id=agent-one&version=2.0.0", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert all(e["version"] == "2.0.0" for e in body["events"])


def test_audit_events_subject_filter(client):
    audit_ledger.append_event("policy_verdict",
                              {"agent_id": "agent-one", "version": "1.0.0"},
                              {"decision": "allow"})
    audit_ledger.append_event("policy_verdict",
                              {"agent_id": "agent-one", "version": "2.0.0"},
                              {"decision": "deny"})
    audit_ledger.append_event("discovery_run", {"run_id": "r1"}, {})
    response = client.get(
        "/api/v1/audit/events?subject_agent_id=agent-one&subject_version=1.0.0",
        headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["events"][0]["subject"]["version"] == "1.0.0"
    # agent_id-only filter returns both versions, never the unrelated event
    body = client.get("/api/v1/audit/events?subject_agent_id=agent-one",
                      headers=HEADERS).json()
    assert body["count"] == 2


def test_skill_version_diff(client):
    skill_registry.create_draft(_skill("skill-one", "1.0.0", instructions="v1 text"))
    skill_registry.create_draft(_skill("skill-one", "2.0.0", instructions="v2 text"))
    response = client.get(
        "/api/v1/skills/skill-one/versions/1.0.0/diff/2.0.0", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "taas.skill-version-diff/v1"
    assert body["record_semantics"] == (
        "structural_diff_of_persisted_manifests_not_behavior_evidence")
    assert body["execution_record"] is False
    assert body["manifest_sha256"]["same"] is False
    changed = {c["path"] for c in body["changes"]["changed_paths"]}
    assert "metadata.version" in changed
    assert "spec.instructions" in changed
    assert body["changes"]["truncated"] is False
    # 404 on a missing version, fail-closed
    assert client.get("/api/v1/skills/skill-one/versions/1.0.0/diff/9.9.9",
                      headers=HEADERS).status_code == 404


def test_skill_version_activity(client):
    skill_registry.create_draft(_skill("skill-one", "1.0.0"))
    response = client.get("/api/v1/skills/skill-one/versions/1.0.0/activity",
                          headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "taas.skill-version-activity/v1"
    assert body["semantics"] == (
        "recorded_governance_activity_not_performance_telemetry"
        "_not_execution_proof")
    assert body["authorization_granted"] is False
    assert body["execution_performed"] is False
    activity = body["recorded_activity"]
    assert activity["lifecycle_events"]["state"] == "recorded"
    assert activity["lifecycle_events"]["count"] == 1  # created event
    assert activity["publisher_signatures"]["state"] == "recorded"
    assert activity["publisher_signatures"]["verified_count"] == 0
    assert activity["revocation"]["state"] == "recorded"
    assert activity["configuration"]["trigger_phrases"] == 1
    assert body["unsupported_metrics"]  # never silently empty
    assert client.get("/api/v1/skills/skill-one/versions/9.9.9/activity",
                      headers=HEADERS).status_code == 404


def test_mcp_snapshot_diff(client):
    snap_a = agent_registry.store_mcp_snapshot({
        "schema_version": "taas.mcp.registry/v1",
        "capture_mode": "test",
        "servers": [{"server_id": "docs", "status": "ok",
                     "protocol_version": "1",
                     "tools": [{"name": "search", "desc": "a"},
                               {"name": "gone", "desc": "x"}]}],
    })
    snap_b = agent_registry.store_mcp_snapshot({
        "schema_version": "taas.mcp.registry/v1",
        "capture_mode": "test",
        "servers": [{"server_id": "docs", "status": "ok",
                     "protocol_version": "1",
                     "tools": [{"name": "search", "desc": "b"},
                               {"name": "new_tool", "desc": "y"}]}],
    })
    response = client.get(
        f"/api/v1/mcp/registry/snapshots/{snap_a['snapshot_id']}"
        f"/diff/{snap_b['snapshot_id']}", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "taas.mcp-snapshot-diff/v1"
    assert body["execution_record"] is False
    assert body["tool_count"] == {"a": 2, "b": 2, "same": True}
    added = body["changes"]["added_paths"]
    removed = body["changes"]["removed_paths"]
    changed = {c["path"] for c in body["changes"]["changed_paths"]}
    assert "servers.docs.tools.new_tool" in added
    assert "servers.docs.tools.gone" in removed
    assert "servers.docs.tools.search.desc" in changed
    # identical snapshot → empty changes
    same = client.get(
        f"/api/v1/mcp/registry/snapshots/{snap_a['snapshot_id']}"
        f"/diff/{snap_a['snapshot_id']}", headers=HEADERS).json()
    assert same["changes"]["added_paths"] == []
    assert same["changes"]["removed_paths"] == []
    assert same["changes"]["changed_paths"] == []
    # invalid id → 422, missing id → 404
    assert client.get("/api/v1/mcp/registry/snapshots/nope/diff/" + "0" * 64,
                      headers=HEADERS).status_code == 422
