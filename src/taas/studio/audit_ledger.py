"""Hash-chained append-only audit ledger for governance events.

Each event carries ``prev_hash`` linking it to the prior event's ``event_hash``;
``verify_chain`` recomputes the chain and reports the first divergence. This is
tamper evidence over recorded events — never proof of execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERIFY_SCHEMA = "taas.audit-verify/v1"
EVENT_TYPES = (
    "evidence", "signature", "approval", "revocation",
    "policy_verdict", "discovery_run",
)
_GENESIS = "0" * 64


def _database_path() -> Path:
    configured = os.environ.get("TAAS_AUDIT_LEDGER_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".taas" / "studio" / "audit.sqlite3").resolve()


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            subject_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL UNIQUE
        )
        """
    )
    return connection


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _event_hash(event_type: str, subject: dict, payload: dict,
                created_at: str, prev_hash: str) -> str:
    body = {"event_type": event_type, "subject": subject, "payload": payload,
            "created_at": created_at, "prev_hash": prev_hash}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def append_event(event_type: str, subject: dict[str, Any],
                 payload: dict[str, Any]) -> dict[str, Any]:
    """Append one event; returns the stored record including its hash."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown audit event type: {event_type}")
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        prev = connection.execute(
            "SELECT event_hash FROM audit_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = prev["event_hash"] if prev else _GENESIS
        event_hash = _event_hash(event_type, subject, payload, created_at, prev_hash)
        connection.execute(
            """
            INSERT INTO audit_events
                (event_type, subject_json, payload_json, created_at, prev_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_type, _canonical(subject), _canonical(payload),
             created_at, prev_hash, event_hash),
        )
    return {
        "event_type": event_type, "subject": subject, "payload": payload,
        "created_at": created_at, "prev_hash": prev_hash, "event_hash": event_hash,
    }


def list_events_page(*, limit: int = 100, event_type: str | None = None,
                     after_seq: int | None = None) -> dict[str, Any]:
    """Keyset-paginated read: ascending ``seq`` order, bounded page size."""
    limit = max(1, min(int(limit), 1000))
    clauses: list[str] = []
    params: list[Any] = []
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if after_seq is not None:
        clauses.append("seq > ?")
        params.append(int(after_seq))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT seq, event_type, subject_json, payload_json, created_at,
                   prev_hash, event_hash
            FROM audit_events {where} ORDER BY seq ASC LIMIT ?
            """,
            (*params, limit + 1),
        ).fetchall()
    has_more = len(rows) > limit
    events = [
        {
            "seq": r["seq"], "event_type": r["event_type"],
            "subject": json.loads(r["subject_json"]),
            "payload": json.loads(r["payload_json"]),
            "created_at": r["created_at"],
            "prev_hash": r["prev_hash"], "event_hash": r["event_hash"],
        }
        for r in rows[:limit]
    ]
    return {
        "events": events,
        "has_more": has_more,
        "next_cursor": events[-1]["seq"] if (has_more and events) else None,
    }


def list_events(*, limit: int = 100, event_type: str | None = None,
                after_seq: int | None = None) -> list[dict[str, Any]]:
    return list_events_page(limit=limit, event_type=event_type,
                            after_seq=after_seq)["events"]


def verify_chain() -> dict[str, Any]:
    """Recompute the hash chain over the entire ledger, in bounded batches."""
    events: list[dict[str, Any]] = []
    cursor: int | None = None
    while True:
        page = list_events_page(limit=1000, after_seq=cursor)
        events.extend(page["events"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    prev_hash = _GENESIS
    first_divergence = None
    for event in events:
        expected = _event_hash(
            event["event_type"], event["subject"], event["payload"],
            event["created_at"], event["prev_hash"],
        )
        if event["prev_hash"] != prev_hash or expected != event["event_hash"]:
            first_divergence = {
                "seq": event["seq"],
                "stored_hash": event["event_hash"],
                "recomputed_hash": expected,
                "expected_prev_hash": prev_hash,
                "stored_prev_hash": event["prev_hash"],
            }
            break
        prev_hash = event["event_hash"]
    return {
        "schema": VERIFY_SCHEMA,
        "event_count": len(events),
        "scan_scope": "full_ledger",
        "chain_valid": first_divergence is None,
        "first_divergence": first_divergence,
        "verify_semantics": "tamper_evidence_over_recorded_events_not_execution_proof",
        "execution_performed": False,
    }
