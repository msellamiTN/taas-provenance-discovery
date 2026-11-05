# Agent Release Readiness — Assurance Evidence & Human Approval

The release-readiness gate (`GET /api/v1/agents/{agent_id}/versions/{version}/release-readiness`)
evaluates deterministic checks against an immutable Agent version. Two checks are
evidence-driven and were previously permanent blockers:

| Check | Satisfied by |
|---|---|
| `trusted_assurance_evidence_verified` | A valid, fresh `provenance_verification` assurance-evidence record bound to the exact release subject |
| `human_approval_record_verified` | A valid, fresh `human_approval` assurance-evidence record bound to the exact release subject |

## Release subject binding

Both record kinds must be bound to the exact identity under review:

```json
{"agent_id": "...", "version": "...",
 "manifest_sha256": "<canonical manifest digest>",
 "registry_snapshot_id": "<content-addressed MCP snapshot or null>"}
```

Evidence recorded for a different manifest digest or snapshot never satisfies the
binding. Recording or tampering with either artifact voids prior approvals — that
is intentional fail-closed behavior.

## Human approval API

`POST /api/v1/agents/{agent_id}/versions/{version}/approvals`

- Requires the Studio bearer token and a `TAAS_EVIDENCE_ATTESTATION_KEY`
  (≥32 bytes); missing key fails closed with HTTP 503.
- Only `validated` or `published` Agent versions can be approved (draft → 409).
- The service attests the record in-process (`issuer: taas-studio`,
  `assessor: TAAS_STUDIO_ACTOR`), stores it in the immutable evidence SQLite
  store, and returns the `evidence_id` plus expiry. `note` (≤1000 chars) and
  `ttl_seconds` (300–2,592,000, default 86,400) are accepted; any other field is
  rejected (`extra=forbid`).

`GET /api/v1/agents/{agent_id}/versions/{version}/approvals` lists verified,
fresh approval records for the current binding; records that fail integrity,
attestation, or freshness checks appear under `invalid_records` and never count.

## Assurance evidence

`provenance_verification` records are produced by trusted in-process assessors
via `assurance_evidence.attest_evidence` + `store_evidence`. There is
deliberately **no public API to mint assessor claims**: the approval endpoint can
only record `human_approval` decisions; it cannot impersonate assessment
evidence. HMAC attestation proves service issuance and integrity — never the
truth of an assessor's claim (`assessor_claim_truth_verified` remains `false`).

## Decision semantics

- `READY` requires *every* check to pass: manifest structure + digest,
  lifecycle, snapshot integrity, tool-grant resolution, assurance evidence, and
  human approval.
- Missing or expired evidence records yield `NEEDS_REVIEW`; manifest,
  lifecycle, snapshot, or grant violations yield `BLOCKED`.
- `READY` is diagnostic only: `authorization_granted`, `execution_enabled`, and
  `human_approval_granted`-style fields remain `false`. No path grants tools,
  permissions, or execution rights.
