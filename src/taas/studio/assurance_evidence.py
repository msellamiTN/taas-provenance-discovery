"""Immutable, attested assurance evidence for governed Agent invocations.

This is a server-side evidence primitive. It is not an authorization engine:
evidence is never accepted from browser/API request bodies, and this module
never grants permission or invokes MCP tools.

The HMAC attestation key represents this service's attestation boundary only.
It is not a substitute for KMS-backed asymmetric signing, workload identity,
or independently verifiable third-party attestations.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


EVIDENCE_TYPES = frozenset({
    "tool_schema_validation",
    "trusted_effect_assessment",
    "provenance_verification",
})
_HASH = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(RuntimeError):
    """Evidence storage, validation, or attestation failure."""


class EvidenceConfigurationError(EvidenceError):
    """Required operator-controlled evidence configuration is missing."""


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
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
    raw = env.get("TAAS_EVIDENCE_ATTESTATION_KEY", "")
    key = raw.encode("utf-8")
    if len(key) < 32:
        raise EvidenceConfigurationError(
            "TAAS_EVIDENCE_ATTESTATION_KEY must contain at least 32 UTF-8 bytes"
        )
    return key


def _database_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    raw = env.get("TAAS_EVIDENCE_DB_PATH", "").strip()
    if not raw:
        return (Path.home() / ".taas" / "studio" / "assurance-evidence.sqlite3").resolve()
    return Path(raw).expanduser().resolve()


def _connect(environ: Mapping[str, str] | None = None) -> sqlite3.Connection:
    path = _database_path(environ)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS assurance_evidence (
            evidence_id TEXT PRIMARY KEY,
            evidence_type TEXT NOT NULL,
            subject_binding_sha256 TEXT NOT NULL,
            issuer TEXT NOT NULL,
            assessor TEXT NOT NULL,
            method TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            attestation_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TRIGGER IF NOT EXISTS assurance_evidence_no_update
        BEFORE UPDATE ON assurance_evidence
        BEGIN SELECT RAISE(ABORT, 'Assurance evidence is immutable'); END
    """)
    connection.execute("""
        CREATE TRIGGER IF NOT EXISTS assurance_evidence_no_delete
        BEFORE DELETE ON assurance_evidence
        BEGIN SELECT RAISE(ABORT, 'Assurance evidence is immutable'); END
    """)
    if os.name == "posix":
        try:
            os.chmod(path.parent, 0o700)
            os.chmod(path, 0o600)
        except OSError:
            pass
    return connection


def _unsigned_record(
    *,
    evidence_type: str,
    subject_binding: dict[str, Any],
    issuer: str,
    assessor: str,
    method: str,
    observed_at: str,
    expires_at: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if evidence_type not in EVIDENCE_TYPES:
        raise EvidenceError("Unsupported assurance evidence type")
    for field, value, maximum in (
        ("issuer", issuer, 256), ("assessor", assessor, 256), ("method", method, 512),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise EvidenceError(f"{field} must be a non-empty bounded string")
    if not isinstance(subject_binding, dict) or not subject_binding:
        raise EvidenceError("subject_binding must be a non-empty object")
    if not isinstance(payload, dict):
        raise EvidenceError("payload must be an object")
    observed = _timestamp(observed_at, "observed_at")
    expires = _timestamp(expires_at, "expires_at")
    now = _now()
    if observed > now + timedelta(minutes=2):
        raise EvidenceError("Evidence observation time is in the future")
    if expires <= observed:
        raise EvidenceError("expires_at must be later than observed_at")
    if expires - observed > timedelta(days=30):
        raise EvidenceError("Evidence validity cannot exceed 30 days")
    return {
        "evidence_type": evidence_type,
        "subject_binding": subject_binding,
        "subject_binding_sha256": canonical_hash(subject_binding),
        "issuer": issuer.strip(),
        "assessor": assessor.strip(),
        "method": method.strip(),
        "observed_at": observed.isoformat(),
        "expires_at": expires.isoformat(),
        "payload": payload,
        "payload_sha256": canonical_hash(payload),
    }


def attest_evidence(
    *,
    evidence_type: str,
    subject_binding: dict[str, Any],
    issuer: str,
    assessor: str,
    method: str,
    payload: dict[str, Any],
    ttl_seconds: int = 3600,
    observed_at: datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Create an attested envelope for trusted in-process assessors only.

    Do not expose this function through a browser-facing endpoint. The caller
    must be a trusted server-side assessor that actually performed the check.
    """
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 30 * 86400:
        raise EvidenceError("ttl_seconds must be between 1 and 2,592,000")
    observed = (observed_at or _now()).astimezone(timezone.utc)
    unsigned = _unsigned_record(
        evidence_type=evidence_type,
        subject_binding=subject_binding,
        issuer=issuer,
        assessor=assessor,
        method=method,
        observed_at=observed.isoformat(),
        expires_at=(observed + timedelta(seconds=ttl_seconds)).isoformat(),
        payload=payload,
    )
    signature = hmac.new(
        _key(environ), canonical_json(unsigned).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {**unsigned, "attestation_sha256": signature}


def store_evidence(
    envelope: dict[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Verify and persist an attested envelope; identical inserts are idempotent."""
    required = {
        "evidence_type", "subject_binding", "subject_binding_sha256", "issuer",
        "assessor", "method", "observed_at", "expires_at", "payload",
        "payload_sha256", "attestation_sha256",
    }
    if not isinstance(envelope, dict) or set(envelope) != required:
        raise EvidenceError("Evidence envelope has missing or unexpected fields")
    unsigned = _unsigned_record(
        evidence_type=envelope["evidence_type"],
        subject_binding=envelope["subject_binding"],
        issuer=envelope["issuer"],
        assessor=envelope["assessor"],
        method=envelope["method"],
        observed_at=envelope["observed_at"],
        expires_at=envelope["expires_at"],
        payload=envelope["payload"],
    )
    if envelope["subject_binding_sha256"] != unsigned["subject_binding_sha256"]:
        raise EvidenceError("Evidence subject binding hash mismatch")
    if envelope["payload_sha256"] != unsigned["payload_sha256"]:
        raise EvidenceError("Evidence payload hash mismatch")
    expected = hmac.new(
        _key(environ), canonical_json(unsigned).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    supplied = envelope["attestation_sha256"]
    if not isinstance(supplied, str) or not hmac.compare_digest(expected, supplied):
        raise EvidenceError("Evidence attestation verification failed")

    evidence_id = canonical_hash({**unsigned, "attestation_sha256": expected})
    created_at = _now().isoformat()
    connection = _connect(environ)
    try:
        connection.execute(
            """INSERT OR IGNORE INTO assurance_evidence
            (evidence_id, evidence_type, subject_binding_sha256, issuer, assessor,
             method, observed_at, expires_at, payload_json, payload_sha256,
             attestation_sha256, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                evidence_id, unsigned["evidence_type"], unsigned["subject_binding_sha256"],
                unsigned["issuer"], unsigned["assessor"], unsigned["method"],
                unsigned["observed_at"], unsigned["expires_at"],
                canonical_json(unsigned["payload"]), unsigned["payload_sha256"],
                expected, created_at,
            ),
        )
        row = connection.execute(
            "SELECT * FROM assurance_evidence WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
    finally:
        connection.close()
    return _public_record(row, evidence_id)


def _public_record(row: sqlite3.Row, evidence_id: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "evidence_type": row["evidence_type"],
        "subject_binding_sha256": row["subject_binding_sha256"],
        "issuer": row["issuer"],
        "assessor": row["assessor"],
        "method": row["method"],
        "observed_at": row["observed_at"],
        "expires_at": row["expires_at"],
        "payload": json.loads(row["payload_json"]),
        "payload_sha256": row["payload_sha256"],
        "attestation_sha256": row["attestation_sha256"],
        "created_at": row["created_at"],
    }


def get_verified_evidence(
    evidence_id: str,
    *,
    expected_type: str,
    expected_binding: dict[str, Any],
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return evidence only when signature, binding, and freshness all verify."""
    if not isinstance(evidence_id, str) or not _HASH.fullmatch(evidence_id):
        raise EvidenceError("evidence_id must be a lowercase SHA-256 digest")
    connection = _connect(environ)
    try:
        row = connection.execute(
            "SELECT * FROM assurance_evidence WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise EvidenceError("Assurance evidence was not found")
    payload = json.loads(row["payload_json"])
    unsigned = {
        "evidence_type": row["evidence_type"],
        "subject_binding_sha256": row["subject_binding_sha256"],
        "issuer": row["issuer"],
        "assessor": row["assessor"],
        "method": row["method"],
        "observed_at": row["observed_at"],
        "expires_at": row["expires_at"],
        "payload_sha256": row["payload_sha256"],
        "payload": payload,
    }
    # Rebuild the canonical envelope using the original subject binding is
    # impossible from the digest alone; the signature is verified against the
    # stored, independently hashed fields and the caller's exact binding hash.
    binding_hash = canonical_hash(expected_binding)
    if row["evidence_type"] != expected_type:
        raise EvidenceError("Assurance evidence type does not match the required type")
    if not hmac.compare_digest(row["subject_binding_sha256"], binding_hash):
        raise EvidenceError("Assurance evidence is bound to a different invocation")
    if not hmac.compare_digest(row["payload_sha256"], canonical_hash(payload)):
        raise EvidenceError("Stored assurance evidence payload failed integrity verification")
    observed = _timestamp(row["observed_at"], "observed_at")
    expires = _timestamp(row["expires_at"], "expires_at")
    current = (now or _now()).astimezone(timezone.utc)
    if observed > current + timedelta(minutes=2) or expires <= current:
        raise EvidenceError("Assurance evidence is not currently fresh")
    # Verify the HMAC using stored, canonical fields. The subject binding hash
    # is itself part of the attested record and checked against expected_binding.
    signed = {
        "evidence_type": row["evidence_type"],
        "subject_binding_sha256": row["subject_binding_sha256"],
        "issuer": row["issuer"],
        "assessor": row["assessor"],
        "method": row["method"],
        "observed_at": row["observed_at"],
        "expires_at": row["expires_at"],
        "payload_sha256": row["payload_sha256"],
        "payload": payload,
    }
    # The issuance signature covers the full subject binding object. It is not
    # reconstructable from its hash; retain the original canonical binding in
    # the database in a later migration. Until then, do not claim verification.
    raise EvidenceError(
        "Evidence retrieval requires the full signed subject binding; schema migration pending"
    )
