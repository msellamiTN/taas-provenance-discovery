# Discovery-Run Persistence

`taas.studio.discovery_runs` — SQLite-backed append-only records for each
`POST /api/v1/objectives/discover` run. A record is an *observation of
pre-execution analysis* — never an execution record.

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/discovery/runs` | Newest-first listing; `limit` (≤500), `status`, `tool_id` filters → `taas.discovery-run-list/v1` |
| `GET /api/v1/discovery/runs/{run_id}` | Full stored record → `taas.discovery-run/v1` |

The discover response gains `discovery_run_id` + `discovery_run_persisted`
so UX can link certificate ↔ run. If persistence itself fails, the response
still succeeds with `discovery_run_id: null` — ids are never fabricated.

## Stored fields

`run_id`, `request_sha256` (canonical request fingerprint),
`goal_spec_sha256`, `tool_source` (`registry_tool_ids`/`request_tools`),
sorted `tool_ids` + `tool_definition_hashes`, `policy_fingerprint`, `status`
(`abstained`/`selected`), `certificate`, `projection_sha256`, `created_at`.
`execution_record: false` is asserted in every fetched record.

## Configuration

- `TAAS_DISCOVERY_RUNS_PATH` — DB location (default `~/.taas/studio/discovery_runs.sqlite3`)
- `TAAS_DISCOVERY_RUNS_MAX_ROWS` — retention bound (default 5000, oldest evicted)

Each recorded run also appends a `discovery_run` event to the hash-chained
audit ledger (see `AUDIT_LEDGER.md`).
