"""SQLite-backed immutable Agent version registry with append-only lifecycle events.

This is a single-service persistence primitive, not a multi-tenant or production
secret-management system. It stores manifest JSON as supplied by the operator.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from taas.studio import json_diff


class AgentRegistryError(RuntimeError):
    """Base error for Agent registry operations."""


class AgentRegistryConflict(AgentRegistryError):
    """An immutable version already exists or a lifecycle transition is invalid."""


class AgentRegistryNotFound(AgentRegistryError):
    """The requested Agent version does not exist."""


def _database_path() -> Path:
    configured = os.environ.get("TAAS_AGENT_REGISTRY_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".taas" / "studio" / "agents.sqlite3").resolve()


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_versions (
            agent_id TEXT NOT NULL,
            version TEXT NOT NULL,
            manifest_json TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            lifecycle_state TEXT NOT NULL CHECK (
                lifecycle_state IN ('draft', 'validated', 'published')
            ),
            registry_snapshot_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (agent_id, version)
        )
        """
    )
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(agent_versions)").fetchall()}
    if "registry_snapshot_id" not in columns:
        connection.execute("ALTER TABLE agent_versions ADD COLUMN registry_snapshot_id TEXT")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_registry_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            server_count INTEGER NOT NULL,
            tool_count INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS mcp_snapshots_no_update
        BEFORE UPDATE ON mcp_registry_snapshots
        BEGIN
            SELECT RAISE(ABORT, 'MCP registry snapshots are immutable');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS mcp_snapshots_no_delete
        BEFORE DELETE ON mcp_registry_snapshots
        BEGIN
            SELECT RAISE(ABORT, 'MCP registry snapshots are immutable');
        END
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            version TEXT NOT NULL,
            event_type TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            actor TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            registry_snapshot_id TEXT,
            FOREIGN KEY (agent_id, version)
                REFERENCES agent_versions(agent_id, version)
        )
        """
    )
    event_columns = {row["name"] for row in connection.execute("PRAGMA table_info(agent_events)").fetchall()}
    if "registry_snapshot_id" not in event_columns:
        connection.execute("ALTER TABLE agent_events ADD COLUMN registry_snapshot_id TEXT")
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_versions_snapshot_bind_once
        BEFORE UPDATE OF registry_snapshot_id ON agent_versions
        WHEN OLD.registry_snapshot_id IS NOT NULL OR NEW.registry_snapshot_id IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'Agent registry snapshot binding is immutable');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_versions_immutable_fields
        BEFORE UPDATE OF agent_id, version, manifest_json, manifest_sha256, created_at
        ON agent_versions
        BEGIN
            SELECT RAISE(ABORT, 'Agent version content is immutable');
        END
        """
    )
    # Lifecycle columns are protected at the engine level, not only by the
    # transition_state() application path: direct SQL cannot bypass transition
    # rules, skip the append-only event record, or silently move updated_at.
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_versions_valid_transition
        BEFORE UPDATE OF lifecycle_state ON agent_versions
        WHEN NOT (
            OLD.lifecycle_state = NEW.lifecycle_state
            OR (OLD.lifecycle_state = 'draft' AND NEW.lifecycle_state = 'validated')
            OR (OLD.lifecycle_state = 'validated' AND NEW.lifecycle_state = 'published')
        )
        BEGIN
            SELECT RAISE(ABORT, 'Invalid Agent lifecycle transition');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_versions_state_requires_event
        AFTER UPDATE OF lifecycle_state ON agent_versions
        WHEN OLD.lifecycle_state <> NEW.lifecycle_state
        BEGIN
            SELECT RAISE(ABORT, 'Agent lifecycle change requires a recorded event')
            WHERE NOT EXISTS (
                SELECT 1 FROM agent_events
                WHERE agent_id = NEW.agent_id AND version = NEW.version
                  AND from_state = OLD.lifecycle_state
                  AND to_state = NEW.lifecycle_state
                  AND manifest_sha256 = NEW.manifest_sha256
                  AND occurred_at = NEW.updated_at
            );
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_versions_updated_at_guard
        BEFORE UPDATE OF updated_at ON agent_versions
        WHEN OLD.lifecycle_state = NEW.lifecycle_state
        BEGIN
            SELECT RAISE(ABORT, 'Agent updated_at may only change with a lifecycle transition');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_versions_no_delete
        BEFORE DELETE ON agent_versions
        BEGIN
            SELECT RAISE(ABORT, 'Agent versions cannot be deleted');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_events_no_update
        BEFORE UPDATE ON agent_events
        BEGIN
            SELECT RAISE(ABORT, 'Agent lifecycle events are append-only');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_events_no_delete
        BEFORE DELETE ON agent_events
        BEGIN
            SELECT RAISE(ABORT, 'Agent lifecycle events are append-only');
        END
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_revocations (
            agent_id TEXT NOT NULL,
            version TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            revoked_by TEXT NOT NULL,
            reason TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            PRIMARY KEY (agent_id, version),
            FOREIGN KEY (agent_id, version)
                REFERENCES agent_versions(agent_id, version)
        )
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_revocations_no_update
        BEFORE UPDATE ON agent_revocations
        BEGIN
            SELECT RAISE(ABORT, 'Agent revocations are immutable');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS agent_revocations_no_delete
        BEFORE DELETE ON agent_revocations
        BEGIN
            SELECT RAISE(ABORT, 'Agent revocations are immutable');
        END
        """
    )
    if os.name == "posix":
        try:
            os.chmod(path.parent, 0o700)
            os.chmod(path, 0o600)
        except OSError:
            pass
    return connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _canonical_manifest(manifest: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return serialized, digest


def _record_event(
    connection: sqlite3.Connection,
    *,
    agent_id: str,
    version: str,
    event_type: str,
    from_state: str | None,
    to_state: str,
    manifest_sha256: str,
    actor: str,
    occurred_at: str,
    registry_snapshot_id: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO agent_events (
            agent_id, version, event_type, from_state, to_state,
            manifest_sha256, actor, occurred_at, registry_snapshot_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (agent_id, version, event_type, from_state, to_state,
         manifest_sha256, actor, occurred_at, registry_snapshot_id),
    )


def create_draft(manifest: dict[str, Any], actor: str = "studio-api") -> dict[str, Any]:
    metadata = manifest["metadata"]
    agent_id, version = metadata["id"], metadata["version"]
    serialized, digest = _canonical_manifest(manifest)
    now = _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """
                INSERT INTO agent_versions (
                    agent_id, version, manifest_json, manifest_sha256,
                    lifecycle_state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'draft', ?, ?)
                """,
                (agent_id, version, serialized, digest, now, now),
            )
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise AgentRegistryConflict(
                f"Agent version {agent_id}@{version} already exists; versions are immutable"
            ) from exc
        _record_event(
            connection, agent_id=agent_id, version=version,
            event_type="agent.created", from_state=None, to_state="draft",
            manifest_sha256=digest, actor=actor, occurred_at=now,
        )
        connection.commit()
    finally:
        connection.close()
    return get_version(agent_id, version)


def get_version(agent_id: str, version: str) -> dict[str, Any]:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM agent_versions WHERE agent_id = ? AND version = ?",
            (agent_id, version),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise AgentRegistryNotFound(f"Agent version {agent_id}@{version} was not found")
    return {
        "agent_id": row["agent_id"],
        "version": row["version"],
        "manifest": json.loads(row["manifest_json"]),
        "manifest_sha256": row["manifest_sha256"],
        "lifecycle_state": row["lifecycle_state"],
        "registry_snapshot_id": row["registry_snapshot_id"],
        "revoked": is_revoked(agent_id, version),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_versions(agent_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    connection = _connect()
    try:
        if agent_id is None:
            rows = connection.execute(
                "SELECT agent_id, version, manifest_sha256, lifecycle_state, registry_snapshot_id, created_at, updated_at "
                "FROM agent_versions ORDER BY created_at DESC, agent_id, version LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT agent_id, version, manifest_sha256, lifecycle_state, registry_snapshot_id, created_at, updated_at "
                "FROM agent_versions WHERE agent_id = ? "
                "ORDER BY created_at DESC, version LIMIT ?",
                (agent_id, limit),
            ).fetchall()
    finally:
        connection.close()
    return {
        "count": len(rows),
        "versions": [dict(row) for row in rows],
        "persistence": "sqlite",
        "tenant_isolation": False,
    }


def transition(
    agent_id: str,
    version: str,
    target_state: str,
    actor: str = "studio-api",
    registry_snapshot_id: str | None = None,
) -> dict[str, Any]:
    allowed = {"draft": "validated", "validated": "published"}
    if target_state not in {"validated", "published"}:
        raise AgentRegistryConflict("Only draft->validated and validated->published transitions are supported")
    if registry_snapshot_id is not None and target_state != "published":
        raise AgentRegistryConflict("MCP registry snapshots may only be bound during publication")
    now = _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT lifecycle_state, manifest_sha256, registry_snapshot_id FROM agent_versions "
            "WHERE agent_id = ? AND version = ?",
            (agent_id, version),
        ).fetchone()
        if row is None:
            connection.rollback()
            raise AgentRegistryNotFound(f"Agent version {agent_id}@{version} was not found")
        current = row["lifecycle_state"]
        if allowed.get(current) != target_state:
            connection.rollback()
            raise AgentRegistryConflict(
                f"Invalid Agent lifecycle transition: {current} -> {target_state}"
            )
        existing_snapshot = row["registry_snapshot_id"]
        if registry_snapshot_id is not None:
            snapshot_row = connection.execute(
                "SELECT 1 FROM mcp_registry_snapshots WHERE snapshot_id = ?",
                (registry_snapshot_id,),
            ).fetchone()
            if snapshot_row is None:
                connection.rollback()
                raise AgentRegistryNotFound(f"MCP registry snapshot {registry_snapshot_id} was not found")
        if registry_snapshot_id is not None and existing_snapshot not in (None, registry_snapshot_id):
            connection.rollback()
            raise AgentRegistryConflict("Agent version is already bound to a different MCP registry snapshot")
        if registry_snapshot_id is not None and existing_snapshot is None:
            connection.execute(
                "UPDATE agent_versions SET registry_snapshot_id = ? WHERE agent_id = ? AND version = ?",
                (registry_snapshot_id, agent_id, version),
            )
        # The event is recorded before the state update: the
        # agent_versions_state_requires_event AFTER-trigger verifies a matching
        # event exists inside this same transaction. If the UPDATE is aborted,
        # the whole transaction rolls back — state and history stay atomic.
        _record_event(
            connection, agent_id=agent_id, version=version,
            event_type=f"agent.{target_state}", from_state=current,
            to_state=target_state, manifest_sha256=row["manifest_sha256"],
            actor=actor, occurred_at=now,
            registry_snapshot_id=registry_snapshot_id or existing_snapshot,
        )
        connection.execute(
            "UPDATE agent_versions SET lifecycle_state = ?, updated_at = ? "
            "WHERE agent_id = ? AND version = ?",
            (target_state, now, agent_id, version),
        )
        connection.commit()
    finally:
        connection.close()
    return get_version(agent_id, version)


def is_revoked(agent_id: str, version: str) -> bool:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT 1 FROM agent_revocations WHERE agent_id = ? AND version = ?",
            (agent_id, version),
        ).fetchone()
    finally:
        connection.close()
    return row is not None


def get_revocation(agent_id: str, version: str) -> dict[str, Any] | None:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT agent_id, version, manifest_sha256, revoked_by, reason, occurred_at "
            "FROM agent_revocations WHERE agent_id = ? AND version = ?",
            (agent_id, version),
        ).fetchone()
    finally:
        connection.close()
    return dict(row) if row is not None else None


def revoke_version(agent_id: str, version: str, *, reason: str,
                   actor: str = "studio-api") -> dict[str, Any]:
    """Record an immutable revocation for an Agent version.

    Revocation never deletes or mutates the version; it marks it unfit for new
    signatures, approvals, or release evaluations. Existing immutable records
    remain inspectable — revocation is a provenance event, not a deletion.
    """
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise AgentRegistryConflict("Revocation reason must be 1-500 characters")
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT lifecycle_state, manifest_sha256 FROM agent_versions "
            "WHERE agent_id = ? AND version = ?",
            (agent_id, version),
        ).fetchone()
        if row is None:
            connection.rollback()
            raise AgentRegistryNotFound(f"Agent version {agent_id}@{version} was not found")
        if row["lifecycle_state"] == "draft":
            connection.rollback()
            raise AgentRegistryConflict("Draft Agent versions cannot be revoked")
        now = _now()
        try:
            connection.execute(
                "INSERT INTO agent_revocations "
                "(agent_id, version, manifest_sha256, revoked_by, reason, occurred_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (agent_id, version, row["manifest_sha256"], actor, reason.strip(), now),
            )
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise AgentRegistryConflict(f"Agent version {agent_id}@{version} is already revoked") from exc
        _record_event(
            connection, agent_id=agent_id, version=version,
            event_type="agent.revoked", from_state=row["lifecycle_state"],
            to_state="revoked", manifest_sha256=row["manifest_sha256"],
            actor=actor, occurred_at=now,
        )
        connection.commit()
    finally:
        connection.close()
    return get_revocation(agent_id, version)


def list_events(agent_id: str | None = None, limit: int = 200) -> dict[str, Any]:
    connection = _connect()
    try:
        if agent_id is None:
            rows = connection.execute(
                "SELECT event_id, agent_id, version, event_type, from_state, to_state, "
                "manifest_sha256, actor, occurred_at, registry_snapshot_id FROM agent_events "
                "ORDER BY event_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT event_id, agent_id, version, event_type, from_state, to_state, "
                "manifest_sha256, actor, occurred_at, registry_snapshot_id FROM agent_events "
                "WHERE agent_id = ? ORDER BY event_id DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
    finally:
        connection.close()
    return {"count": len(rows), "events": [dict(row) for row in rows]}


def diff_versions(agent_id: str, version_a: str, version_b: str) -> dict[str, Any]:
    """Structural manifest diff between two immutable versions of one Agent.

    Compares stored manifests only — it proves nothing about runtime behavior;
    it reports how two recorded configurations differ.
    """
    va = get_version(agent_id, version_a)
    vb = get_version(agent_id, version_b)
    out = json_diff.walk_diff(va["manifest"], vb["manifest"])
    return {
        "schema": "taas.agent-version-diff/v1",
        "agent_id": agent_id,
        "version_a": version_a,
        "version_b": version_b,
        "manifest_sha256": {"a": va["manifest_sha256"], "b": vb["manifest_sha256"],
                            "same": va["manifest_sha256"] == vb["manifest_sha256"]},
        "lifecycle_state": {"a": va["lifecycle_state"], "b": vb["lifecycle_state"]},
        "registry_snapshot_id": {"a": va["registry_snapshot_id"],
                                 "b": vb["registry_snapshot_id"],
                                 "same": va["registry_snapshot_id"] == vb["registry_snapshot_id"]},
        "changes": {
            "added_paths": out["added"],
            "removed_paths": out["removed"],
            "changed_paths": out["changed"],
            "truncated": out["truncated"],
        },
        "record_semantics": "structural_diff_of_persisted_manifests_not_behavior_evidence",
        "execution_record": False,
    }


def store_mcp_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Persist a content-addressed read-only MCP schema snapshot."""
    serialized, snapshot_id = _canonical_manifest(snapshot)
    servers = snapshot.get("servers", [])
    tool_count = sum(len(server.get("tools", [])) for server in servers)
    created_at = _now()
    connection = _connect()
    try:
        connection.execute(
            "INSERT OR IGNORE INTO mcp_registry_snapshots "
            "(snapshot_id, snapshot_json, created_at, server_count, tool_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (snapshot_id, serialized, created_at, len(servers), tool_count),
        )
        row = connection.execute(
            "SELECT created_at, server_count, tool_count FROM mcp_registry_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
    finally:
        connection.close()
    return {
        "snapshot_id": snapshot_id,
        "created_at": row["created_at"],
        "server_count": row["server_count"],
        "tool_count": row["tool_count"],
        "snapshot": snapshot,
    }


def get_mcp_snapshot(snapshot_id: str) -> dict[str, Any]:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM mcp_registry_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise AgentRegistryNotFound(f"MCP registry snapshot {snapshot_id} was not found")
    snapshot = json.loads(row["snapshot_json"])
    _, recomputed_id = _canonical_manifest(snapshot)
    if recomputed_id != row["snapshot_id"]:
        raise AgentRegistryError("Stored MCP registry snapshot failed its content hash check")
    return {
        "snapshot_id": row["snapshot_id"],
        "created_at": row["created_at"],
        "server_count": row["server_count"],
        "tool_count": row["tool_count"],
        "snapshot": snapshot,
    }


def list_mcp_snapshots(limit: int = 100) -> dict[str, Any]:
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT snapshot_id, created_at, server_count, tool_count "
            "FROM mcp_registry_snapshots ORDER BY created_at DESC, snapshot_id LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        connection.close()
    return {"count": len(rows), "snapshots": [dict(row) for row in rows]}
