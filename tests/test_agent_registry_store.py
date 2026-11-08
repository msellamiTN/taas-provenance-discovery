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


def test_lifecycle_columns_reject_direct_sql_mutation(monkeypatch, tmp_path):
    """Direct SQL cannot bypass transition rules, event recording, or updated_at."""
    database = tmp_path / "agents.sqlite3"
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(database))
    agent_registry.create_draft(_manifest())

    connection = agent_registry._connect()
    try:
        # Invalid transition (draft -> published) is rejected at the engine level.
        with pytest.raises(sqlite3.IntegrityError, match="Invalid Agent lifecycle transition"):
            connection.execute(
                "UPDATE agent_versions SET lifecycle_state = 'published', "
                "updated_at = 'x' WHERE agent_id = 'audit-agent' AND version = '1.0.0'"
            )
        # A valid-looking transition without a recorded event is rejected too.
        with pytest.raises(sqlite3.IntegrityError, match="requires a recorded event"):
            connection.execute(
                "UPDATE agent_versions SET lifecycle_state = 'validated', "
                "updated_at = 'x' WHERE agent_id = 'audit-agent' AND version = '1.0.0'"
            )
        # updated_at cannot move without a lifecycle transition.
        with pytest.raises(sqlite3.IntegrityError, match="updated_at may only change"):
            connection.execute(
                "UPDATE agent_versions SET updated_at = '2999-01-01T00:00:00.000+00:00' "
                "WHERE agent_id = 'audit-agent' AND version = '1.0.0'"
            )
        # State and history are unchanged after all three failed statements.
        row = connection.execute(
            "SELECT lifecycle_state, updated_at FROM agent_versions "
            "WHERE agent_id = 'audit-agent' AND version = '1.0.0'"
        ).fetchone()
        assert row["lifecycle_state"] == "draft"
        events = connection.execute(
            "SELECT to_state FROM agent_events "
            "WHERE agent_id = 'audit-agent' AND version = '1.0.0'"
        ).fetchall()
        assert [e["to_state"] for e in events] == ["draft"]
    finally:
        connection.close()


def test_transition_rolls_back_atomically_and_state_matches_last_event(monkeypatch, tmp_path):
    database = tmp_path / "agents.sqlite3"
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(database))
    agent_registry.create_draft(_manifest())

    validated = agent_registry.transition("audit-agent", "1.0.0", "validated")
    assert validated["lifecycle_state"] == "validated"
    published = agent_registry.transition("audit-agent", "1.0.0", "published")
    assert published["lifecycle_state"] == "published"

    # A stale transition attempt (published -> validated is unsupported) fails
    # and must not append an event or touch updated_at.
    with pytest.raises(agent_registry.AgentRegistryConflict):
        agent_registry.transition("audit-agent", "1.0.0", "validated")
    after = agent_registry.get_version("audit-agent", "1.0.0")
    assert after["lifecycle_state"] == "published"
    assert after["updated_at"] == published["updated_at"]

    events = agent_registry.list_events("audit-agent")["events"]
    assert [e["to_state"] for e in events] == ["published", "validated", "draft"]
    # Stored state equals the latest recorded event's to_state.
    assert after["lifecycle_state"] == events[0]["to_state"]


def test_skill_lifecycle_columns_reject_direct_sql_mutation(monkeypatch, tmp_path):
    from taas.studio import skill_registry

    database = tmp_path / "skills.sqlite3"
    monkeypatch.setenv("TAAS_SKILL_REGISTRY_PATH", str(database))
    skill_registry.create_draft({
        "apiVersion": "taas.ai/v1alpha1", "kind": "Skill",
        "metadata": {"id": "sk-audit", "name": "Audit", "version": "1.0.0"},
        "spec": {"instructions": "i"},
    })

    connection = skill_registry._connect()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="Invalid Skill lifecycle transition"):
            connection.execute(
                "UPDATE skill_versions SET lifecycle_state = 'published', "
                "updated_at = 'x' WHERE skill_id = 'sk-audit' AND version = '1.0.0'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="requires a recorded event"):
            connection.execute(
                "UPDATE skill_versions SET lifecycle_state = 'validated', "
                "updated_at = 'x' WHERE skill_id = 'sk-audit' AND version = '1.0.0'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="updated_at may only change"):
            connection.execute(
                "UPDATE skill_versions SET updated_at = '2999-01-01T00:00:00.000+00:00' "
                "WHERE skill_id = 'sk-audit' AND version = '1.0.0'"
            )
    finally:
        connection.close()

    # The legitimate path still works end-to-end through the service.
    validated = skill_registry.transition("sk-audit", "1.0.0", "validated")
    assert validated["lifecycle_state"] == "validated"


def test_concurrent_lifecycle_transitions_serialize_fail_closed(monkeypatch, tmp_path):
    """Two racing transitions cannot both win; BEGIN IMMEDIATE serializes the
    write and the loser re-reads committed state, failing with a conflict."""
    import threading

    database = tmp_path / "agents.sqlite3"
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(database))
    agent_registry.create_draft(_manifest())

    results: dict[str, str] = {}

    def race(name: str) -> None:
        try:
            agent_registry.transition("audit-agent", "1.0.0", "validated")
            results[name] = "ok"
        except agent_registry.AgentRegistryConflict:
            results[name] = "conflict"

    threads = [threading.Thread(target=race, args=(f"t{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    # Exactly one transition wins; the rest fail closed on committed state.
    assert list(results.values()).count("ok") == 1
    assert list(results.values()).count("conflict") == 3
    assert agent_registry.get_version("audit-agent", "1.0.0")["lifecycle_state"] == "validated"
    # Exactly one validated event recorded — no divergence between state and log.
    events = agent_registry.list_events("audit-agent")["events"]
    assert [e["to_state"] for e in events] == ["validated", "draft"]
