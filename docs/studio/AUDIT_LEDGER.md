# Hash-Chained Audit Ledger

`taas.studio.audit_ledger` — append-only event log where each event's
`prev_hash` links to the prior event's `event_hash` (genesis = 64 zeros).
`event_hash` is `sha256` over the canonical `{event_type, subject, payload,
created_at, prev_hash}` — so any edit to a stored row invalidates it and the
chain after it.

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/audit/events` | Oldest-first listing; `limit` (≤1000), `event_type` filter → `taas.audit-events/v1` |
| `GET /api/v1/audit/verify` | Recompute the chain; report `chain_valid` + `first_divergence` (seq, stored vs recomputed hashes) → `taas.audit-verify/v1` |

## Event types

`evidence`, `signature`, `approval`, `revocation`, `policy_verdict`,
`discovery_run`. Today wired: `discovery_run` (each persisted run) and
`approval` (each recorded human approval — subject = `{agent_id, version,
evidence_id}`).

## Semantics

Tamper evidence over *recorded* events — it proves the log was not modified
since write; it does not prove the events' claims and is never execution
proof (`execution_performed: false`). `TAAS_AUDIT_LEDGER_PATH` sets the DB
location (default `~/.taas/studio/audit.sqlite3`).
