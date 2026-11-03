# Trusted assurance evidence service

## Scope

This milestone adds a server-side, append-only evidence store and an attested
evidence envelope. It does **not** authorize an invocation, issue an approval,
or call MCP `tools/call`.

Supported evidence categories:

- `tool_schema_validation`
- `trusted_effect_assessment`
- `provenance_verification`

An evidence record carries a subject binding, issuer, assessor, method,
observation time, expiry, payload digest, and an HMAC attestation. Evidence
records are content-addressed and protected against SQL UPDATE/DELETE.

## Trust boundary

Only trusted in-process assessors may call `attest_evidence`. Do not expose
that function through a browser-facing route or accept its envelope from an
untrusted client. The attestation key is loaded from
`TAAS_EVIDENCE_ATTESTATION_KEY` and must contain at least 32 UTF-8 bytes.

Configure `TAAS_EVIDENCE_DB_PATH` to select the SQLite database. The default
is `~/.taas/studio/assurance-evidence.sqlite3`.

The HMAC key proves that this service created the envelope; it does not prove
that the assessor's underlying claim is true. Assessor identity and method
must be established by the trusted server-side integration. HMAC is a
single-service integrity mechanism, not a replacement for KMS-backed signing,
workload identity, or independent attestations.

## Invocation binding

The intended subject binding is the complete immutable invocation identity:

- Agent ID, version, manifest digest
- MCP snapshot digest, server ID, tool name, tool-definition digest
- Canonical argument digest and GoalSpec digest
- Principal identity and policy version/digest

Evidence must be rejected when any bound field differs. Freshness is checked
at read time, not merely at ingestion. Evidence expiry is limited to 30 days.

## Current limitation

This branch is a storage/attestation foundation only. The read path verifies the stored full canonical subject binding, the payload
digest, the HMAC attestation, the content-addressed evidence ID, the requested
evidence type, and current freshness. Legacy rows without a persisted signed
subject binding are rejected. Tests cover tampering, binding mismatch, expiry,
type substitution, and idempotent replay.

The authorization preflight must continue to deny until all required evidence
types, argument-schema validation, trusted effect assessment, human identity,
human approval, and durable authorization/audit controls are integrated.
MCP execution remains disabled.
