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
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (agent_id, version)
        )
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
            FOREIGN KEY (agent_id, version)
                REFERENCES agent_versions(agent_id, version)
        )
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
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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
) -> None:
    connection.execute(
        """
        INSERT INTO agent_events (
            agent_id, version, event_type, from_state, to_state,
            manifest_sha256, actor, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (agent_id, version, event_type, from_state, to_state,
         manifest_sha256, actor, occurred_at),
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
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_versions(agent_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    connection = _connect()
    try:
        if agent_id is None:
            rows = connection.execute(
                "SELECT agent_id, version, manifest_sha256, lifecycle_state, created_at, updated_at "
                "FROM agent_versions ORDER BY created_at DESC, agent_id, version LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT agent_id, version, manifest_sha256, lifecycle_state, created_at, updated_at "
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
) -> dict[str, Any]:
    allowed = {"draft": "validated", "validated": "published"}
    if target_state not in {"validated", "published"}:
        raise AgentRegistryConflict("Only draft->validated and validated->published transitions are supported")
    now = _now()
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
        current = row["lifecycle_state"]
        if allowed.get(current) != target_state:
            connection.rollback()
            raise AgentRegistryConflict(
                f"Invalid Agent lifecycle transition: {current} -> {target_state}"
            )
        connection.execute(
            "UPDATE agent_versions SET lifecycle_state = ?, updated_at = ? "
            "WHERE agent_id = ? AND version = ?",
            (target_state, now, agent_id, version),
        )
        _record_event(
            connection, agent_id=agent_id, version=version,
            event_type=f"agent.{target_state}", from_state=current,
            to_state=target_state, manifest_sha256=row["manifest_sha256"],
            actor=actor, occurred_at=now,
        )
        connection.commit()
    finally:
        connection.close()
    return get_version(agent_id, version)


def list_events(agent_id: str | None = None, limit: int = 200) -> dict[str, Any]:
    connection = _connect()
    try:
        if agent_id is None:
            rows = connection.execute(
                "SELECT event_id, agent_id, version, event_type, from_state, to_state, "
                "manifest_sha256, actor, occurred_at FROM agent_events "
                "ORDER BY event_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT event_id, agent_id, version, event_type, from_state, to_state, "
                "manifest_sha256, actor, occurred_at FROM agent_events "
                "WHERE agent_id = ? ORDER BY event_id DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
    finally:
        connection.close()
    return {"count": len(rows), "events": [dict(row) for row in rows]}
