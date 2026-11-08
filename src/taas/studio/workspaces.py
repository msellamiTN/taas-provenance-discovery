"""SQLite-backed durable workspace drafts.

A workspace draft is authored intent state (GoalSpec, discovery request,
notes) that a user explicitly saves and restores. Drafts are never
discovery results, approval records, or execution evidence — they carry
no semantic-correctness or runtime claims. Single-service store matching
the discovery-runs convention; it is not multi-tenant.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from taas.studio import json_diff

WORKSPACE_SCHEMA = "taas.workspace-draft/v1"
WORKSPACE_LIST_SCHEMA = "taas.workspace-list/v1"
_DEFAULT_MAX_ROWS = 200


def _database_path() -> Path:
    configured = os.environ.get("TAAS_WORKSPACES_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".taas" / "studio" / "workspaces.sqlite3").resolve()


def _max_rows() -> int:
    try:
        return max(1, int(os.environ.get("TAAS_WORKSPACES_MAX_ROWS", _DEFAULT_MAX_ROWS)))
    except ValueError:
        return _DEFAULT_MAX_ROWS


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            draft_json TEXT NOT NULL,
            draft_sha256 TEXT NOT NULL,
            revision INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspaces_updated ON workspaces(updated_at)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_revisions (
            workspace_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            draft_sha256 TEXT NOT NULL,
            actor TEXT NOT NULL,
            changes_json TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            PRIMARY KEY (workspace_id, revision),
            FOREIGN KEY (workspace_id)
                REFERENCES workspaces(workspace_id) ON DELETE CASCADE
        )
        """
    )
    return connection


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evict_oldest(connection: sqlite3.Connection) -> int:
    max_rows = _max_rows()
    row = connection.execute("SELECT COUNT(*) AS n FROM workspaces").fetchone()
    excess = row["n"] - max_rows
    if excess <= 0:
        return 0
    connection.execute(
        "DELETE FROM workspaces WHERE workspace_id IN ("
        "SELECT workspace_id FROM workspaces ORDER BY updated_at ASC LIMIT ?)",
        (excess,),
    )
    return excess


def _row_to_workspace(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": WORKSPACE_SCHEMA,
        "workspace_id": row["workspace_id"],
        "name": row["name"],
        "draft": json.loads(row["draft_json"]),
        "draft_sha256": row["draft_sha256"],
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "record_semantics": "authored_draft_not_analysis_not_execution",
    }


def _record_revision(connection: sqlite3.Connection, *, workspace_id: str,
                     revision: int, draft_sha256: str, actor: str,
                     changes: dict[str, Any]) -> None:
    """Append the immutable per-revision provenance record.

    Records who changed which field paths and to what digest — an edit
    history, never evidence that the draft content is correct or executed.
    """
    connection.execute(
        """
        INSERT INTO workspace_revisions (
            workspace_id, revision, draft_sha256, actor, changes_json, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (workspace_id, revision, draft_sha256, actor,
         _canonical(changes), _now()),
    )


def create_workspace(*, name: str, draft: dict[str, Any],
                   actor: str = "studio-api") -> dict[str, Any]:
    """Explicitly save a new draft; nothing is persisted implicitly."""
    workspace_id = uuid.uuid4().hex
    now = _now()
    digest = _sha256(draft)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id, name, draft_json, draft_sha256, revision,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (workspace_id, name, _canonical(draft), digest, 1, now, now),
        )
        _record_revision(
            connection, workspace_id=workspace_id, revision=1,
            draft_sha256=digest, actor=actor,
            changes={"kind": "created",
                     "added_paths": json_diff.walk_diff({}, draft)["added"]},
        )
        _evict_oldest(connection)
    return get_workspace(workspace_id)  # type: ignore[return-value]


def list_workspaces(*, limit: int = 100) -> dict[str, Any]:
    """Metadata-only listing (draft bodies excluded), newest first."""
    limit = max(1, min(int(limit), 500))
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT workspace_id, name, draft_sha256, revision, created_at, updated_at
            FROM workspaces ORDER BY updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return {
        "schema": WORKSPACE_LIST_SCHEMA,
        "workspaces": [
            {
                "workspace_id": r["workspace_id"],
                "name": r["name"],
                "draft_sha256": r["draft_sha256"],
                "revision": r["revision"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ],
        "count": len(rows),
        "limit": limit,
        "record_semantics": "authored_draft_metadata_not_analysis_not_execution",
    }


def get_workspace(workspace_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
    return _row_to_workspace(row) if row else None


def update_workspace(
    workspace_id: str, *, name: str | None, draft: dict[str, Any], revision: int,
    actor: str = "studio-api",
) -> dict[str, Any] | None:
    """Optimistic-concurrency update; returns None if id unknown.

    Raises ``RevisionConflictError`` when the caller's revision is stale —
    the draft is never silently overwritten.
    """
    new_digest = _sha256(draft)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT revision, name, draft_json FROM workspaces WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        if row is None:
            return None
        if row["revision"] != revision:
            raise RevisionConflictError(
                f"workspace revision {row['revision']} != supplied {revision}"
            )
        previous = json.loads(row["draft_json"])
        diff = json_diff.walk_diff(previous, draft)
        changes = {
            "kind": "updated",
            "added_paths": diff["added"],
            "removed_paths": diff["removed"],
            "changed_paths": diff["changed"],
            "truncated": diff["truncated"],
            "renamed": bool(name) and name != row["name"],
        }
        connection.execute(
            """
            UPDATE workspaces
            SET name = ?, draft_json = ?, draft_sha256 = ?,
                revision = revision + 1, updated_at = ?
            WHERE workspace_id = ?
            """,
            (
                name or row["name"],
                _canonical(draft),
                new_digest,
                _now(),
                workspace_id,
            ),
        )
        _record_revision(
            connection, workspace_id=workspace_id, revision=revision + 1,
            draft_sha256=new_digest, actor=actor, changes=changes,
        )
    return get_workspace(workspace_id)


def list_revisions(workspace_id: str, *, limit: int = 100) -> dict[str, Any] | None:
    """Immutable per-revision edit history for one workspace draft."""
    limit = max(1, min(int(limit), 500))
    with _connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM workspaces WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        if exists is None:
            return None
        rows = connection.execute(
            """
            SELECT revision, draft_sha256, actor, changes_json, occurred_at
            FROM workspace_revisions WHERE workspace_id = ?
            ORDER BY revision DESC LIMIT ?
            """,
            (workspace_id, limit),
        ).fetchall()
    return {
        "schema": "taas.workspace-revision-history/v1",
        "workspace_id": workspace_id,
        "count": len(rows),
        "revisions": [
            {
                "revision": r["revision"],
                "draft_sha256": r["draft_sha256"],
                "actor": r["actor"],
                "changes": json.loads(r["changes_json"]),
                "occurred_at": r["occurred_at"],
            }
            for r in rows
        ],
        "record_semantics": "authored_edit_history_not_correctness_not_execution",
    }


class RevisionConflictError(Exception):
    """Raised when an update supplies a stale revision number."""


def delete_workspace(workspace_id: str) -> bool:
    """Explicit delete only; returns True when a draft was removed."""
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM workspaces WHERE workspace_id = ?", (workspace_id,)
        )
        return cursor.rowcount > 0
