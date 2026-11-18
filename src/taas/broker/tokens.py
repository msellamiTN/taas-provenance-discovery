"""Opaque token store — issued tokens are random handles backed by claims.

The outward token carries nothing; introspection resolves it. Store is
sqlite so broker replicas share state (HA per PAD §7.7); TTL enforced on
read, never extended by introspection.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any


def _store_path() -> Path:
    configured = os.environ.get("TAAS_BROKER_TOKEN_STORE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".taas" / "broker" / "tokens.sqlite3").resolve()


def _connect() -> sqlite3.Connection:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            handle TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            scope TEXT NOT NULL,
            audience TEXT NOT NULL,
            cnf_jkt TEXT,
            issued_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    return con


def issue(subject: str, scope: str, audience: str, ttl_seconds: int = 120,
          cnf_jkt: str | None = None) -> dict[str, Any]:
    """Issue an opaque token handle bound to (subject, downscoped scope)."""
    handle = secrets.token_urlsafe(32)
    now = int(time.time())
    with _connect() as con:
        con.execute(
            "INSERT INTO tokens (handle, subject, scope, audience, cnf_jkt, issued_at, expires_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (handle, subject, scope, audience, cnf_jkt, now, now + ttl_seconds))
    return {"access_token": handle, "token_type": "Bearer",
            "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "expires_in": ttl_seconds, "scope": scope,
            **({"cnf": {"jkt": cnf_jkt}} if cnf_jkt else {})}


def introspect(handle: str) -> dict[str, Any] | None:
    """Resolve an opaque handle → active claims, or None (unknown/expired)."""
    with _connect() as con:
        row = con.execute(
            "SELECT subject, scope, audience, cnf_jkt, expires_at FROM tokens"
            " WHERE handle = ?", (handle,)).fetchone()
    if row is None or row["expires_at"] <= int(time.time()):
        return None
    return {"active": True, "sub": row["subject"], "scope": row["scope"],
            "aud": row["audience"], "cnf_jkt": row["cnf_jkt"],
            "exp": row["expires_at"]}
