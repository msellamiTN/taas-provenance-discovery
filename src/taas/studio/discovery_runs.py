"""SQLite-backed append-only persistence for pre-execution discovery runs.

Records are observations of analysis that already happened — they are never
execution proofs. The store is a single-service primitive matching the Agent
registry convention; it is not multi-tenant.
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

RUN_SCHEMA = "taas.discovery-run/v1"
RUN_LIST_SCHEMA = "taas.discovery-run-list/v1"
_DEFAULT_MAX_ROWS = 5000


def _database_path() -> Path:
    configured = os.environ.get("TAAS_DISCOVERY_RUNS_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".taas" / "studio" / "discovery_runs.sqlite3").resolve()


def _max_rows() -> int:
    try:
        return max(1, int(os.environ.get("TAAS_DISCOVERY_RUNS_MAX_ROWS", _DEFAULT_MAX_ROWS)))
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
        CREATE TABLE IF NOT EXISTS discovery_runs (
            run_id TEXT PRIMARY KEY,
            request_sha256 TEXT NOT NULL,
            goal_spec_sha256 TEXT NOT NULL,
            tool_source TEXT NOT NULL,
            tool_ids_json TEXT NOT NULL,
            tool_hashes_json TEXT NOT NULL,
            policy_fingerprint TEXT,
            status TEXT NOT NULL,
            certificate_json TEXT,
            projection_sha256 TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovery_runs_status ON discovery_runs(status)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovery_runs_created ON discovery_runs(created_at)"
    )
    return connection


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _evict_oldest(connection: sqlite3.Connection) -> int:
    """Bounded retention: evict oldest runs beyond the configured cap."""
    max_rows = _max_rows()
    row = connection.execute("SELECT COUNT(*) AS n FROM discovery_runs").fetchone()
    excess = row["n"] - max_rows
    if excess <= 0:
        return 0
    connection.execute(
        "DELETE FROM discovery_runs WHERE run_id IN ("
        "SELECT run_id FROM discovery_runs ORDER BY created_at ASC LIMIT ?)",
        (excess,),
    )
    return excess


def record_discovery_run(
    *,
    goal_spec: dict[str, Any],
    request: dict[str, Any],
    tool_source: str,
    tool_ids: list[str],
    tool_hashes: dict[str, str] | None = None,
    policy_fingerprint: str | None,
    status: str,
    certificate: dict[str, Any] | None,
    hypergraph_projection: dict[str, Any] | None,
) -> str:
    """Append one discovery-run record; returns the generated run id."""
    run_id = uuid.uuid4().hex
    projection_hash = _sha256(hypergraph_projection) if hypergraph_projection else None
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO discovery_runs (
                run_id, request_sha256, goal_spec_sha256, tool_source,
                tool_ids_json, tool_hashes_json, policy_fingerprint, status,
                certificate_json, projection_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, _sha256(request), _sha256(goal_spec), tool_source,
                _canonical(sorted(tool_ids)),
                _canonical(tool_hashes or {}),
                policy_fingerprint, status,
                _canonical(certificate) if certificate else None,
                projection_hash,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        _evict_oldest(connection)
    return run_id


def list_discovery_runs(
    *, limit: int = 50, status: str | None = None, tool_id: str | None = None,
) -> dict[str, Any]:
    """Read-only listing, newest first. Bounded by ``limit``."""
    limit = max(1, min(int(limit), 500))
    where, params = [], []
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if tool_id is not None:
        where.append("tool_ids_json LIKE ?")
        params.append(f'%"{tool_id}"%')
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT run_id, goal_spec_sha256, tool_source, tool_ids_json, status,
                   projection_sha256, created_at
            FROM discovery_runs {clause}
            ORDER BY created_at DESC LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        total = connection.execute(
            f"SELECT COUNT(*) AS n FROM discovery_runs {clause}", params
        ).fetchone()["n"]
    return {
        "schema": RUN_LIST_SCHEMA,
        "runs": [
            {
                "run_id": r["run_id"],
                "goal_spec_sha256": r["goal_spec_sha256"],
                "tool_source": r["tool_source"],
                "tool_ids": json.loads(r["tool_ids_json"]),
                "status": r["status"],
                "projection_sha256": r["projection_sha256"],
                "created_at": r["created_at"],
            }
            for r in rows
        ],
        "total_matching": total,
        "limit": limit,
        "record_semantics": "observation_of_pre_execution_analysis_not_execution",
    }


def get_discovery_run(run_id: str) -> dict[str, Any] | None:
    """Full stored record for one run; None when unknown."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM discovery_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    if row is None:
        return None
    return {
        "schema": RUN_SCHEMA,
        "run_id": row["run_id"],
        "request_sha256": row["request_sha256"],
        "goal_spec_sha256": row["goal_spec_sha256"],
        "tool_source": row["tool_source"],
        "tool_ids": json.loads(row["tool_ids_json"]),
        "tool_definition_hashes": json.loads(row["tool_hashes_json"]),
        "policy_fingerprint": row["policy_fingerprint"],
        "status": row["status"],
        "certificate": json.loads(row["certificate_json"]) if row["certificate_json"] else None,
        "projection_sha256": row["projection_sha256"],
        "created_at": row["created_at"],
        "record_semantics": "observation_of_pre_execution_analysis_not_execution",
        "execution_record": False,
    }


def diff_discovery_runs(run_id_a: str, run_id_b: str) -> dict[str, Any] | None:
    """Field-level diff of two persisted run envelopes. None when either is unknown.

    Compares stored digests and tool pins only — it re-runs nothing and proves
    nothing about execution; it reports how two recorded analyses differed.
    """
    a = get_discovery_run(run_id_a)
    b = get_discovery_run(run_id_b)
    if a is None or b is None:
        return None

    def _pin_map(run: dict[str, Any]) -> dict[str, str | None]:
        return {tid: run["tool_definition_hashes"].get(tid) for tid in run["tool_ids"]}

    pins_a, pins_b = _pin_map(a), _pin_map(b)
    ids_a, ids_b = set(pins_a), set(pins_b)
    changed_hash = sorted(
        tid for tid in ids_a & ids_b if pins_a[tid] != pins_b[tid]
    )
    digest_fields = (
        "request_sha256", "goal_spec_sha256",
        "policy_fingerprint", "projection_sha256",
    )
    return {
        "schema": "taas.discovery-run-diff/v1",
        "run_id_a": run_id_a,
        "run_id_b": run_id_b,
        "digests": {
            field: {
                "a": a.get(field),
                "b": b.get(field),
                "same": a.get(field) == b.get(field),
            }
            for field in digest_fields
        },
        "status": {"a": a.get("status"), "b": b.get("status"),
                   "same": a.get("status") == b.get("status")},
        "tools": {
            "added_in_b": sorted(ids_b - ids_a),
            "removed_in_b": sorted(ids_a - ids_b),
            "definition_hash_changed": changed_hash,
            "count_a": len(ids_a),
            "count_b": len(ids_b),
        },
        "created_at": {"a": a.get("created_at"), "b": b.get("created_at")},
        "record_semantics": "diff_of_persisted_analysis_envelopes_not_execution",
        "execution_record": False,
    }
