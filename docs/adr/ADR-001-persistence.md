# ADR-001 — Persistence layer for TaaS Studio (OD-1)

| Field | Value |
|---|---|
| Status | **Proposed** — awaiting decision owner sign-off |
| Decides | Megaplan OD-1 · prerequisite for all Phase B work |
| Context docs | `ARCHITECTURE_REVIEW.md` F12 · `REQUIREMENTS_GAP.md` FR-OBS-6 row |

## Context

TaaS Studio persists to per-domain SQLite files today:

| Store | Env var | Access pattern |
|---|---|---|
| audit ledger | `TAAS_AUDIT_LEDGER_PATH` | append-only, hot writes, verify reads |
| agent / skill registries | `TAAS_{AGENT,SKILL}_REGISTRY_PATH` | mixed read/write |
| workspaces / discovery runs / evidence / api keys | `TAAS_*_PATH` | mixed read/write |
| audit anchors | `TAAS_AUDIT_ANCHOR_PATH` | append-only JSON, separate key |

This is correct for single-process alpha. Phase B adds: the MCP proxy and
token broker as *separate deployables*, broker HA replicas, and concurrent
writers. SQLite's single-writer file lock and host-local path are the hard
limit. Deferred too long, the store choice gets made by accident (F12).

## Decision

**Adopt a two-tier store contract; Postgres as the Phase B primary.**

1. **Store interface per domain.** Each persistence module keeps its current
   Python API (`append_event`, `list_events_page`, `load_processed`, …) —
   **API contracts and route shapes do not change** (NFR-SCL-3).
2. **PostgreSQL primary** for governed environments: multi-writer, real
   transactions, `LISTEN/NOTIFY` for change feeds (needed later by the proxy's
   registry watches), managed offerings on all three clouds (RDS/Cloud
   SQL/Azure Database) — consistent with the per-env capability matrix.
3. **SQLite remains the embedded profile** for dev/test/Colab — same
   interface, single connection; `sqlite://`/`postgres://` selected by a
   `TAAS_STORE_DSN` env var, per domain.
4. **Audit events in an append-only table** (`INSERT`-only role grants,
   no `UPDATE`/`DELETE` in the app role) — the DB enforces what the hash
   chain assumes. Anchors continue to live **outside** the store (D12:
   producer never sole anchor).
5. **Migration**: `scripts/migrate_sqlite_to_postgres.py` reads each sqlite
   store and replays rows in seq order; audit chain re-verified post-migration
   before cutover. File stores remain readable for rollback.

## Alternatives considered

- **Object store + indexing** — rejected as primary: no transactions for
  registry writes, no listen/notify, anchors-as-objects solves only audit.
  Retained as the *anchor/evidence-blob* tier (WORM fits naturally).
- **Event-sourced log (Kafka-class) as system of record** — rejected for
  now: operational weight exceeds Phase B need; revisited if SIEM streaming
  (FR-OBS-5) becomes the primary path.
- **Keep SQLite everywhere** — rejected for governed envs: single writer,
  host-local file, no HA story. Retained as the dev/embedded profile.

## Consequences

- Phase B work (broker replicas, proxy watches, four-eyes flows) has a
  real concurrency model instead of file locks.
- `TAAS_STORE_DSN` per domain allows splitting audit onto a dedicated,
  permission-locked instance while registries share another.
- Anchor artifacts and evidence blobs move to WORM-capable object storage
  — unchanged code paths, different path target.

## Implementation order (Phase B, when approved)

1. Store interface + `TAAS_STORE_DSN` plumbing (sqlite default — no behavior change).
2. Postgres adapter per domain; `audit_events` INSERT-only grants.
3. Migration script + post-migration `verify_chain` gate.
4. Anchor/evidence blobs → object-store path.

**Decision needed:** approve Postgres-primary + sqlite-embedded profile,
or select object-store-primary (records why if chosen).
