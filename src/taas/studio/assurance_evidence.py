"""Immutable, attested assurance evidence for governed Agent invocations.

This server-side primitive never authorizes an invocation or calls MCP tools.
HMAC proves service issuance/integrity, not the truth of an assessor's claim.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

EVIDENCE_TYPES = frozenset({
    "tool_schema_validation", "trusted_effect_assessment", "provenance_verification",
    "human_approval",
    "publisher_signature",
})
_HASH = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(RuntimeError):
    """Evidence storage, validation, or attestation failure."""


class EvidenceConfigurationError(EvidenceError):
    """Required operator-controlled evidence configuration is missing."""


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise EvidenceError("Evidence must contain strict JSON values") from exc


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise EvidenceError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise EvidenceError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _key(environ: Mapping[str, str] | None = None) -> bytes:
    env = os.environ if environ is None else environ
    key = env.get("TAAS_EVIDENCE_ATTESTATION_KEY", "").encode("utf-8")
    if len(key) < 32:
        raise EvidenceConfigurationError(
            "TAAS_EVIDENCE_ATTESTATION_KEY must contain at least 32 UTF-8 bytes"
        )
    return key


def _database_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    raw = env.get("TAAS_EVIDENCE_DB_PATH", "").strip()
    return (Path(raw).expanduser().resolve() if raw else
            (Path.home() / ".taas" / "studio" / "assurance-evidence.sqlite3").resolve())


def _connect(environ: Mapping[str, str] | None = None) -> sqlite3.Connection:
    path = _database_path(environ)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS assurance_evidence (
        evidence_id TEXT PRIMARY KEY, evidence_type TEXT NOT NULL,
        subject_binding_json TEXT NOT NULL, subject_binding_sha256 TEXT NOT NULL,
        issuer TEXT NOT NULL, assessor TEXT NOT NULL, method TEXT NOT NULL,
        observed_at TEXT NOT NULL, expires_at TEXT NOT NULL,
        payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
        attestation_sha256 TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    columns = {row["name"] for row in db.execute(
        "PRAGMA table_info(assurance_evidence)").fetchall()}
    if "subject_binding_json" not in columns:
        db.execute("ALTER TABLE assurance_evidence ADD COLUMN subject_binding_json TEXT")
    db.execute("""CREATE TRIGGER IF NOT EXISTS assurance_evidence_no_update
        BEFORE UPDATE ON assurance_evidence
        BEGIN SELECT RAISE(ABORT, 'Assurance evidence is immutable'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS assurance_evidence_no_delete
        BEFORE DELETE ON assurance_evidence
        BEGIN SELECT RAISE(ABORT, 'Assurance evidence is immutable'); END""")
    if os.name == "posix":
        try:
            os.chmod(path.parent, 0o700)
            os.chmod(path, 0o600)
        except OSError:
            pass
    return db


def _unsigned(*, evidence_type: str, subject_binding: dict[str, Any],
              issuer: str, assessor: str, method: str, observed_at: str,
              expires_at: str, payload: dict[str, Any]) -> dict[str, Any]:
    if evidence_type not in EVIDENCE_TYPES:
        raise EvidenceError("Unsupported assurance evidence type")
    for name, value, limit in (("issuer", issuer, 256), ("assessor", assessor, 256),
                               ("method", method, 512)):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise EvidenceError(f"{name} must be a non-empty bounded string")
    if not isinstance(subject_binding, dict) or not subject_binding:
        raise EvidenceError("subject_binding must be a non-empty object")
    if not isinstance(payload, dict):
        raise EvidenceError("payload must be an object")
    observed, expires = _timestamp(observed_at, "observed_at"), _timestamp(expires_at, "expires_at")
    if observed > _now() + timedelta(minutes=2):
        raise EvidenceError("Evidence observation time is in the future")
    if expires <= observed:
        raise EvidenceError("expires_at must be later than observed_at")
    if expires - observed > timedelta(days=30):
        raise EvidenceError("Evidence validity cannot exceed 30 days")
    return {
        "evidence_type": evidence_type,
        "subject_binding": subject_binding,
        "subject_binding_sha256": canonical_hash(subject_binding),
        "issuer": issuer.strip(), "assessor": assessor.strip(), "method": method.strip(),
        "observed_at": observed.isoformat(), "expires_at": expires.isoformat(),
        "payload": payload, "payload_sha256": canonical_hash(payload),
    }


def attest_evidence(*, evidence_type: str, subject_binding: dict[str, Any],
                    issuer: str, assessor: str, method: str, payload: dict[str, Any],
                    ttl_seconds: int = 3600, observed_at: datetime | None = None,
                    environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Attest evidence from a trusted in-process assessor; never expose as public API."""
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 2592000:
        raise EvidenceError("ttl_seconds must be between 1 and 2,592,000")
    observed = observed_at or _now()
    if observed.tzinfo is None:
        raise EvidenceError("observed_at must include a timezone")
    observed = observed.astimezone(timezone.utc)
    unsigned = _unsigned(
        evidence_type=evidence_type, subject_binding=subject_binding, issuer=issuer,
        assessor=assessor, method=method, observed_at=observed.isoformat(),
        expires_at=(observed + timedelta(seconds=ttl_seconds)).isoformat(), payload=payload,
    )
    signature = hmac.new(_key(environ), canonical_json(unsigned).encode(), hashlib.sha256).hexdigest()
    return {**unsigned, "attestation_sha256": signature}


def _verify_envelope(envelope: dict[str, Any], environ: Mapping[str, str] | None) -> dict[str, Any]:
    required = {"evidence_type", "subject_binding", "subject_binding_sha256", "issuer",
                "assessor", "method", "observed_at", "expires_at", "payload",
                "payload_sha256", "attestation_sha256"}
    if not isinstance(envelope, dict) or set(envelope) != required:
        raise EvidenceError("Evidence envelope has missing or unexpected fields")
    unsigned = _unsigned(
        evidence_type=envelope["evidence_type"], subject_binding=envelope["subject_binding"],
        issuer=envelope["issuer"], assessor=envelope["assessor"], method=envelope["method"],
        observed_at=envelope["observed_at"], expires_at=envelope["expires_at"],
        payload=envelope["payload"],
    )
    for field in ("subject_binding_sha256", "payload_sha256"):
        if envelope[field] != unsigned[field]:
            raise EvidenceError(f"Evidence {field} mismatch")
    expected = hmac.new(_key(environ), canonical_json(unsigned).encode(), hashlib.sha256).hexdigest()
    supplied = envelope["attestation_sha256"]
    if not isinstance(supplied, str) or not hmac.compare_digest(expected, supplied):
        raise EvidenceError("Evidence attestation verification failed")
    return unsigned


def _record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "evidence_id": row["evidence_id"], "evidence_type": row["evidence_type"],
        "subject_binding": json.loads(row["subject_binding_json"]),
        "subject_binding_sha256": row["subject_binding_sha256"],
        "issuer": row["issuer"], "assessor": row["assessor"], "method": row["method"],
        "observed_at": row["observed_at"], "expires_at": row["expires_at"],
        "payload": json.loads(row["payload_json"]), "payload_sha256": row["payload_sha256"],
        "attestation_sha256": row["attestation_sha256"], "created_at": row["created_at"],
    }


def store_evidence(envelope: dict[str, Any], *,
                   environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Verify and persist an attested envelope; identical inserts are idempotent."""
    unsigned = _verify_envelope(envelope, environ)
    signature = envelope["attestation_sha256"]
    evidence_id = canonical_hash({**unsigned, "attestation_sha256": signature})
    db = _connect(environ)
    try:
        db.execute("""INSERT OR IGNORE INTO assurance_evidence
            (evidence_id, evidence_type, subject_binding_json, subject_binding_sha256,
             issuer, assessor, method, observed_at, expires_at, payload_json,
             payload_sha256, attestation_sha256, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, unsigned["evidence_type"], canonical_json(unsigned["subject_binding"]),
             unsigned["subject_binding_sha256"], unsigned["issuer"], unsigned["assessor"],
             unsigned["method"], unsigned["observed_at"], unsigned["expires_at"],
             canonical_json(unsigned["payload"]), unsigned["payload_sha256"], signature,
             _now().isoformat()))
        row = db.execute("SELECT * FROM assurance_evidence WHERE evidence_id=?",
                         (evidence_id,)).fetchone()
    finally:
        db.close()
    return _record(row)


def get_verified_evidence(evidence_id: str, *, expected_type: str,
                          expected_binding: dict[str, Any],
                          environ: Mapping[str, str] | None = None,
                          now: datetime | None = None) -> dict[str, Any]:
    """Verify signature, exact subject binding, record integrity, and freshness."""
    if not isinstance(evidence_id, str) or not _HASH.fullmatch(evidence_id):
        raise EvidenceError("evidence_id must be a lowercase SHA-256 digest")
    db = _connect(environ)
    try:
        row = db.execute("SELECT * FROM assurance_evidence WHERE evidence_id=?",
                         (evidence_id,)).fetchone()
    finally:
        db.close()
    if row is None:
        raise EvidenceError("Assurance evidence was not found")
    if row["subject_binding_json"] is None:
        raise EvidenceError("Legacy evidence lacks a signed subject binding and cannot be trusted")
    record = _record(row)
    if record["evidence_type"] != expected_type:
        raise EvidenceError("Assurance evidence type does not match the required type")
    if canonical_json(record["subject_binding"]) != canonical_json(expected_binding):
        raise EvidenceError("Assurance evidence is bound to a different invocation")
    unsigned = _unsigned(
        evidence_type=record["evidence_type"], subject_binding=record["subject_binding"],
        issuer=record["issuer"], assessor=record["assessor"], method=record["method"],
        observed_at=record["observed_at"], expires_at=record["expires_at"],
        payload=record["payload"],
    )
    if unsigned["subject_binding_sha256"] != record["subject_binding_sha256"]:
        raise EvidenceError("Stored subject binding failed integrity verification")
    if unsigned["payload_sha256"] != record["payload_sha256"]:
        raise EvidenceError("Stored payload failed integrity verification")
    expected_signature = hmac.new(
        _key(environ), canonical_json(unsigned).encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, record["attestation_sha256"]):
        raise EvidenceError("Stored evidence attestation verification failed")
    expected_id = canonical_hash({**unsigned, "attestation_sha256": expected_signature})
    if not hmac.compare_digest(expected_id, evidence_id):
        raise EvidenceError("Stored evidence content address mismatch")
    current = now or _now()
    if current.tzinfo is None:
        raise EvidenceError("Verification time must include a timezone")
    current = current.astimezone(timezone.utc)
    observed, expires = _timestamp(record["observed_at"], "observed_at"), _timestamp(record["expires_at"], "expires_at")
    if observed > current + timedelta(minutes=2) or expires <= current:
        raise EvidenceError("Assurance evidence is not currently fresh")
    return record


def list_verified_evidence_for_subject(subject_binding: dict[str, Any], *,
                                       expected_type: str | None = None,
                                       environ: Mapping[str, str] | None = None,
                                       now: datetime | None = None) -> dict[str, Any]:
    """Return every stored record bound to an exact subject, verified independently.

    Each record is re-verified for integrity, attestation and freshness. Records
    that fail verification are reported under ``invalid`` with a bounded reason;
    they never count as satisfied evidence.
    """
    if not isinstance(subject_binding, dict) or not subject_binding:
        raise EvidenceError("subject_binding must be a non-empty object")
    binding_hash = canonical_hash(subject_binding)
    db = _connect(environ)
    try:
        rows = db.execute(
            "SELECT evidence_id, evidence_type FROM assurance_evidence "
            "WHERE subject_binding_sha256=? ORDER BY created_at DESC",
            (binding_hash,),
        ).fetchall()
    finally:
        db.close()
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for row in rows:
        if expected_type is not None and row["evidence_type"] != expected_type:
            continue
        try:
            record = inspect_verified_evidence(row["evidence_id"], environ=environ, now=now)
        except EvidenceError as exc:
            invalid.append({"evidence_id": row["evidence_id"], "reason": str(exc)})
            continue
        valid.append(record)
    return {"count": len(valid), "valid": valid, "invalid": invalid}


def inspect_verified_evidence(evidence_id: str, *,
                              environ: Mapping[str, str] | None = None,
                              now: datetime | None = None) -> dict[str, Any]:
    """Return a record after verifying its stored binding, signature, digest and freshness.

    The stored binding is the comparison target; callers cannot supply or replace it.
    This proves record integrity and freshness, not assessor truth.
    """
    if not isinstance(evidence_id, str) or not _HASH.fullmatch(evidence_id):
        raise EvidenceError("evidence_id must be a lowercase SHA-256 digest")
    db = _connect(environ)
    try:
        row = db.execute(
            "SELECT * FROM assurance_evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise EvidenceError("Assurance evidence was not found")
    record = _record(row)
    return get_verified_evidence(
        evidence_id, expected_type=record["evidence_type"],
        expected_binding=record["subject_binding"], environ=environ, now=now,
    )
