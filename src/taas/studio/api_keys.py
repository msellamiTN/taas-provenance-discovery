"""Named Studio API keys — per-key actor identity with hashed storage.

A named key authenticates a caller and binds subsequent writes to its
declared ``actor``. Keys are credentials, not authorization: possessing a
key proves who is calling, never what they may do — policy verdicts,
approvals, signatures and execution remain separate governance records.

Plaintext tokens are returned exactly once at creation; only the SHA-256
digest persists. Revocation is a recorded lifecycle state, not deletion —
the key row (minus any secret material, which never exists at rest)
remains for audit. Single-service store matching the workspaces /
discovery-runs convention; it is not multi-tenant.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KEY_LIST_SCHEMA = "taas.api-key-list/v1"
_KEY_ID_RE = re.compile(r"^ak_[0-9a-f]{16}$")
_ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,63}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.@-]{0,127}$")


class ApiKeyError(Exception):
    """Base error for API-key store operations."""


class ApiKeyNotFoundError(ApiKeyError):
    pass


class ApiKeyAlreadyRevokedError(ApiKeyError):
    pass


def _database_path() -> Path:
    configured = os.environ.get("TAAS_API_KEYS_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".taas" / "studio" / "api_keys.sqlite3").resolve()


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            actor TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            revoked_at TEXT,
            revoked_by TEXT,
            last_used_at TEXT
        )
        """
    )
    return connection


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _public_record(row: sqlite3.Row) -> dict[str, Any]:
    """Metadata only — never the hash, never any token material."""
    return {
        "key_id": row["key_id"],
        "name": row["name"],
        "actor": row["actor"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "revoked_at": row["revoked_at"],
        "revoked_by": row["revoked_by"],
        "last_used_at": row["last_used_at"],
        "state": "revoked" if row["revoked_at"] else "active",
    }


def validate_actor(actor: str) -> str:
    actor = actor.strip()
    if not _ACTOR_RE.match(actor):
        raise ApiKeyError(
            "actor must be 1-64 chars of [A-Za-z0-9_.@-], starting alphanumeric")
    return actor


def validate_name(name: str) -> str:
    name = name.strip()
    if not _NAME_RE.match(name):
        raise ApiKeyError(
            "name must be 1-128 chars of [A-Za-z0-9 _.@-], starting alphanumeric")
    return name


def create_api_key(*, name: str, actor: str, created_by: str) -> dict[str, Any]:
    """Create a named key; returns the record plus the plaintext token once."""
    name = validate_name(name)
    actor = validate_actor(actor)
    created_by = validate_actor(created_by)
    key_id = "ak_" + secrets.token_hex(8)
    token = "taas_" + secrets.token_hex(32)
    now = _utcnow()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO api_keys
                (key_id, name, actor, key_hash, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key_id, name, actor, _hash_token(token), created_by, now),
        )
    record = get_api_key(key_id)
    assert record is not None
    return {
        **record,
        "token": token,
        "token_displayed_once": True,
        "plaintext_persisted": False,
    }


def get_api_key(key_id: str) -> dict[str, Any] | None:
    if not _KEY_ID_RE.match(key_id):
        return None
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM api_keys WHERE key_id = ?", (key_id,)
        ).fetchone()
    return _public_record(row) if row else None


def list_api_keys(*, include_revoked: bool = True, limit: int = 200) -> dict[str, Any]:
    limit = max(1, min(int(limit), 1000))
    clauses = "" if include_revoked else "WHERE revoked_at IS NULL"
    with _connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM api_keys {clauses} ORDER BY created_at DESC, key_id "
            "LIMIT ?",
            (limit,),
        ).fetchall()
        active = connection.execute(
            "SELECT COUNT(*) AS n FROM api_keys WHERE revoked_at IS NULL"
        ).fetchone()["n"]
    return {
        "schema": KEY_LIST_SCHEMA,
        "keys": [_public_record(row) for row in rows],
        "active_count": active,
        "total_matching": len(rows),
        "credential_semantics": (
            "authentication_credentials_not_authorization_not_execution"),
    }


def revoke_api_key(key_id: str, *, revoked_by: str) -> dict[str, Any]:
    """Record revocation; the row is retained, never deleted."""
    if not _KEY_ID_RE.match(key_id):
        raise ApiKeyNotFoundError(f"Unknown API key: {key_id}")
    revoked_by = validate_actor(revoked_by)
    now = _utcnow()
    with _connect() as connection:
        row = connection.execute(
            "SELECT revoked_at FROM api_keys WHERE key_id = ?", (key_id,)
        ).fetchone()
        if row is None:
            raise ApiKeyNotFoundError(f"Unknown API key: {key_id}")
        if row["revoked_at"] is not None:
            raise ApiKeyAlreadyRevokedError(f"API key already revoked: {key_id}")
        connection.execute(
            "UPDATE api_keys SET revoked_at = ?, revoked_by = ? WHERE key_id = ?",
            (now, revoked_by, key_id),
        )
    record = get_api_key(key_id)
    assert record is not None
    return record


def lookup_active_key(token: str) -> dict[str, Any] | None:
    """Return the active key record for a presented token, else None.

    Only the SHA-256 digest is compared; plaintext tokens are never stored.
    Updates ``last_used_at`` on successful match.
    """
    if not token or not token.startswith("taas_"):
        return None
    digest = _hash_token(token)
    now = _utcnow()
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
            (digest,),
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
            (now, row["key_id"]),
        )
    return _public_record(row)


def has_any_keys() -> bool:
    """True when the keystore holds at least one key (active or revoked)."""
    try:
        with _connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM api_keys"
            ).fetchone()
        return bool(row and row["n"])
    except sqlite3.Error:
        return False


def active_key_count() -> int:
    try:
        with _connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM api_keys WHERE revoked_at IS NULL"
            ).fetchone()
        return int(row["n"]) if row else 0
    except sqlite3.Error:
        return 0


def key_counts() -> dict[str, int]:
    """Active/total named-key counts; zeros when the store is unreachable."""
    try:
        with _connect() as connection:
            rows = connection.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN revoked_at IS NULL THEN 1 ELSE 0 END) AS active "
                "FROM api_keys"
            ).fetchone()
        return {"active": int(rows["active"] or 0), "total": int(rows["total"] or 0)}
    except sqlite3.Error:
        return {"active": 0, "total": 0}
