"""Signed audit anchors — D12 phase 1.

The ledger's local hash chain is tamper-evident but self-attested: whoever
writes the file can rewrite and re-chain it. An anchor records the chain
head ``(seq, event_hash)`` under a separate signing key into a separate
artifact file. Verifying an anchor re-reads the event stored at that seq:

- ``intact`` — the stored event at the anchored seq still hashes identically
- ``advanced`` — intact anchor plus newer events appended after it (expected)
- ``tampered`` — the event at the anchored seq changed, or the ledger was
  truncated below it → history rewritten

This is the local half of D12. Writing anchors to WORM/witness storage and
streaming events to SIEM are the transport half — a Phase B seam. The file
and the key are separated so a rewritten ledger cannot reforge old anchors.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import audit_ledger

ANCHOR_SCHEMA = "taas.audit-anchor/v1"
_KEY_ENV = "TAAS_AUDIT_ANCHOR_KEY"
_PATH_ENV = "TAAS_AUDIT_ANCHOR_PATH"


def _anchors_path() -> Path:
    configured = os.environ.get(_PATH_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return audit_ledger._database_path().with_name("audit.anchors.json")


def _signing_key() -> bytes:
    raw = os.environ.get(_KEY_ENV, "").strip()
    if not raw:
        raise ValueError(
            f"Audit anchoring requires {_KEY_ENV} — deliberately separate from "
            "the ledger so a rewritten chain cannot reforge anchors")
    return raw.encode("utf-8")


def _chain_head() -> dict[str, Any]:
    """Last committed (seq, event_hash) — genesis when the ledger is empty."""
    with audit_ledger._connect() as connection:
        row = connection.execute(
            "SELECT seq, event_hash FROM audit_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return {"seq": 0, "event_hash": audit_ledger._GENESIS}
    return {"seq": int(row["seq"]), "event_hash": row["event_hash"]}


def _event_hash_at(seq: int) -> str | None:
    with audit_ledger._connect() as connection:
        row = connection.execute(
            "SELECT event_hash FROM audit_events WHERE seq = ?", (seq,)
        ).fetchone()
    return row["event_hash"] if row else None


def _digest(record: dict[str, Any], key: bytes) -> str:
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def create_anchor() -> dict[str, Any]:
    """Sign the current chain head and append it to the anchor artifact."""
    head = _chain_head()
    record = {
        "schema": ANCHOR_SCHEMA,
        "seq": head["seq"],
        "head_hash": head["event_hash"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    record["digest"] = _digest(
        {k: record[k] for k in ("schema", "seq", "head_hash", "created_at")},
        _signing_key())
    path = _anchors_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    anchors = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    anchors.append(record)
    path.write_text(json.dumps(anchors, indent=2), encoding="utf-8")
    # The anchor event itself advances the head — it is chained like any other
    # event so its own existence is tamper-evident.
    audit_ledger.append_event("audit_anchor",
                              {"kind": "audit_anchor", "seq": head["seq"]},
                              {"anchored_seq": head["seq"],
                               "anchored_hash": head["event_hash"],
                               "digest": record["digest"]})
    return record


def verify_anchor(anchor: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify the latest (or given) anchor against the live ledger."""
    if anchor is None:
        path = _anchors_path()
        anchors = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
        if not anchors:
            return {"schema": ANCHOR_SCHEMA, "status": "no_anchors", "anchor": None}
        anchor = anchors[-1]
    signed = {k: anchor[k] for k in ("schema", "seq", "head_hash", "created_at")}
    try:
        signature_ok = hmac.compare_digest(
            _digest(signed, _signing_key()), anchor.get("digest", ""))
    except ValueError:
        signature_ok = False
    seq = anchor["seq"]
    stored = _event_hash_at(seq) if seq > 0 else audit_ledger._GENESIS
    if stored is None:
        status = "tampered"          # ledger truncated below the anchor
    elif not signature_ok:
        status = "tampered"          # anchor artifact itself forged
    elif stored != anchor["head_hash"]:
        status = "tampered"          # history at seq rewritten + re-chained
    else:
        status = "intact" if _chain_head()["seq"] == seq else "advanced"
    return {
        "schema": ANCHOR_SCHEMA,
        "status": status,
        "signature_ok": signature_ok,
        "anchor": anchor,
        "current_head": _chain_head(),
        "semantics": "anchor_proves_anchored_history_not_post_anchor_events",
    }
