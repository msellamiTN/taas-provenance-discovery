import os
import sqlite3
import stat

import pytest

from taas.studio import agent_registry


def _manifest():
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "id": "audit-agent",
            "name": "Audit Agent",
            "version": "1.0.0",
            "description": "",
        },
        "spec": {
            "model": {
                "provider": "huggingface",
                "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
            },
            "instructions": "Summarize records for the operator.",
            "goal_spec_template": None,
            "tool_allowlist": [],
            "resources": {
                "max_new_tokens": 512,
                "timeout_seconds": 60,
                "max_tool_calls": 0,
            },
            "approval": {
                "require_human_approval": True,
                "require_assurance": True,
                "allow_side_effects": False,
            },
        },
    }


def test_sqlite_registry_prevents_version_content_mutation_and_deletion(monkeypatch, tmp_path):
    database = tmp_path / "private" / "agents.sqlite3"
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(database))
    created = agent_registry.create_draft(_manifest())
    assert created["lifecycle_state"] == "draft"

    connection = agent_registry._connect()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="content is immutable"):
            connection.execute(
                "UPDATE agent_versions SET manifest_json = '{}' "
                "WHERE agent_id = 'audit-agent' AND version = '1.0.0'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute(
                "DELETE FROM agent_versions WHERE agent_id = 'audit-agent'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE agent_events SET actor = 'tampered' WHERE agent_id = 'audit-agent'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM agent_events WHERE agent_id = 'audit-agent'"
            )
    finally:
        connection.close()

    # Lifecycle columns remain mutable only through the transition service.
    validated = agent_registry.transition("audit-agent", "1.0.0", "validated")
    assert validated["lifecycle_state"] == "validated"


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permissions only")
def test_sqlite_registry_applies_owner_only_permissions(monkeypatch, tmp_path):
    database = tmp_path / "private" / "agents.sqlite3"
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(database))
    agent_registry.create_draft(_manifest())
    assert stat.S_IMODE(database.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(database.stat().st_mode) == 0o600


def test_mcp_registry_snapshot_rows_are_immutable(monkeypatch, tmp_path):
    import sqlite3

    from taas.studio import agent_registry

    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    snapshot = {
        "schema_version": "taas.mcp.registry/v1",
        "capture_mode": "test",
        "servers": [],
    }
    stored = agent_registry.store_mcp_snapshot(snapshot)
    assert agent_registry.get_mcp_snapshot(stored["snapshot_id"])["snapshot"] == snapshot

    connection = agent_registry._connect()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="snapshots are immutable"):
            connection.execute(
                "UPDATE mcp_registry_snapshots SET snapshot_json = '{}' WHERE snapshot_id = ?",
                (stored["snapshot_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="snapshots are immutable"):
            connection.execute(
                "DELETE FROM mcp_registry_snapshots WHERE snapshot_id = ?",
                (stored["snapshot_id"],),
            )
    finally:
        connection.close()


def test_mcp_snapshot_read_detects_content_hash_tampering(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    stored = agent_registry.store_mcp_snapshot({
        "schema_version": "taas.mcp.registry/v1",
        "capture_mode": "test",
        "servers": [],
    })
    connection = agent_registry._connect()
    try:
        connection.execute("DROP TRIGGER mcp_snapshots_no_update")
        connection.execute(
            "UPDATE mcp_registry_snapshots SET snapshot_json = '{}' WHERE snapshot_id = ?",
            (stored["snapshot_id"],),
        )
    finally:
        connection.close()

    with pytest.raises(agent_registry.AgentRegistryError, match="content hash check"):
        agent_registry.get_mcp_snapshot(stored["snapshot_id"])


def test_registry_migrates_existing_agent_tables_to_snapshot_binding(monkeypatch, tmp_path):
    database = tmp_path / "legacy" / "agents.sqlite3"
    database.parent.mkdir()
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE agent_versions (
                agent_id TEXT NOT NULL,
                version TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                lifecycle_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (agent_id, version)
            );
            CREATE TABLE agent_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                actor TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            """
        )
    finally:
        connection.close()

    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(database))
    connection = agent_registry._connect()
    try:
        version_columns = {row["name"] for row in connection.execute("PRAGMA table_info(agent_versions)")}
        event_columns = {row["name"] for row in connection.execute("PRAGMA table_info(agent_events)")}
        assert "registry_snapshot_id" in version_columns
        assert "registry_snapshot_id" in event_columns
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='mcp_registry_snapshots'"
        ).fetchone() is not None
    finally:
        connection.close()
