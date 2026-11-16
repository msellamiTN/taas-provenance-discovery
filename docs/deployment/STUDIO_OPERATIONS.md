# TaaS Studio — Operations Runbook (S3 + O1)

Scope: single-instance preproduction deployment of `taas.studio.api:app`
(FastAPI + SQLite). Multi-instance or multi-tenant deployment is out of
scope — it requires a Postgres adapter and is a separate project.

## 1. Deployment

### Environment-driven configuration

All state locations and credentials come from environment variables; nothing
secret is stored in the repository or image.

| Variable | Default | Purpose |
|---|---|---|
| `TAAS_STUDIO_API_TOKEN` | — (required or keys must exist) | Shared bootstrap bearer token |
| `TAAS_STUDIO_ACTOR` | `studio-operator` | Actor stamped when the shared token is used |
| `TAAS_API_KEYS_PATH` | `~/.taas/studio/api_keys.sqlite3` | Named API key store (S1) |
| `TAAS_AUDIT_LEDGER_PATH` | `~/.taas/studio/audit.sqlite3` | Hash-chained audit ledger |
| `TAAS_AGENT_REGISTRY_PATH` | `~/.taas/studio/agents.sqlite3` | Agent versions + signatures |
| `TAAS_SKILL_REGISTRY_PATH` | `~/.taas/studio/skills.sqlite3` | Skill versions + signatures |
| `TAAS_WORKSPACES_PATH` | `~/.taas/studio/workspaces.sqlite3` | Workspaces + revision history |
| `TAAS_DISCOVERY_RUNS_PATH` | `~/.taas/studio/runs.sqlite3` | Persisted discovery runs |
| `TAAS_EVIDENCE_DB_PATH` | `~/.taas/studio/evidence.sqlite3` | Signed assurance evidence |
| `TAAS_EVIDENCE_ATTESTATION_KEY` | — (required for sign/approve) | HMAC key for evidence signatures; **persist it** — rotating invalidates verification of records signed under the old key |
| `TAAS_MODEL_PROFILE` | unset | Optional model profile override |
| `TAAS_MCP_SERVERS_JSON` / `TAAS_MCP_SERVERS_FILE` | unset | Operator-configured MCP stdio servers (inspection only, never `tools/call`) |

### Launch

```bash
export TAAS_STUDIO_API_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export TAAS_EVIDENCE_ATTESTATION_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
# persist the attestation key somewhere durable BEFORE first sign operation
python -m uvicorn taas.studio.api:app --host 127.0.0.1 --port 8000
```

- Bind loopback or an authenticated reverse proxy/tunnel only. The UI (`/`)
  and API share the origin; there is deliberately **no CORS middleware** —
  browsers cannot call the API cross-origin.
- `GET /health` = process liveness; `GET /ready` = dependency check.
- Every response carries `X-Request-ID` (echoed or generated). Request bodies
  are capped at 2 MiB (413 beyond). Security headers: `nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.

## 2. Authentication & key rotation (S1)

Credentials, in precedence order: named API key (`taas_<64hex>` bearer) →
shared `TAAS_STUDIO_API_TOKEN` → fail-closed 503 when neither exists.

```bash
# create a named key (requires current valid credential)
curl -X POST $BASE/api/v1/admin/api-keys \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"ci-runner","actor":"ci-bot","expires_at":"2027-01-01T00:00:00Z"}'
# -> {"key_id":"ak_...","token":"taas_..."}  (plaintext shown ONCE)

curl $BASE/api/v1/admin/api-keys -H "Authorization: Bearer $TOKEN"   # list (hashes never returned)
curl -X POST $BASE/api/v1/admin/api-keys/ak_.../revoke -H "Authorization: Bearer $TOKEN"
```

Rotation procedure:
1. Create the new key; distribute plaintext out-of-band.
2. Verify the new key works (`GET /api/v1/platform/overview`).
3. Revoke the old key; confirm it now returns 401.
4. Audit trail: `api_key` events (`created`/`revoked`) are in the ledger —
   `GET /api/v1/audit/events?event_type=api_key`.

Shared-token rotation: set a new `TAAS_STUDIO_API_TOKEN`, restart, revoke
nothing (token has no record) — prefer migrating fully to named keys and
unsetting the shared token once all callers hold keys (keys-only mode is
already supported: unset `TAAS_STUDIO_API_TOKEN` after keys exist).

Attestation-key rotation is **destructive to verifiability**: evidence signed
under the old key fails freshness/verification. Only rotate with a planned
re-signing migration; otherwise treat the key as long-lived secret material.

## 3. Backup & restore (S3)

All durable state is SQLite. Use the **online backup API** — it is safe on a
live database and produces a consistent snapshot (verified: `integrity_check`
= ok, row counts identical).

```python
import sqlite3, pathlib
STORES = ["audit", "agents", "skills", "workspaces", "runs", "evidence", "api_keys"]
BASE = pathlib.Path(os.environ.get("TAAS_DATA_DIR", "~/.taas/studio")).expanduser()
for name in STORES:
    src_path = BASE / f"{name}.sqlite3"
    if not src_path.exists():
        continue
    dst_path = BASE / "backups" / f"{name}-{stamp}.sqlite3"
    src, dst = sqlite3.connect(src_path), sqlite3.connect(dst_path)
    src.backup(dst); dst.close(); src.close()
```

Equivalent CLI (stopped service only): `sqlite3 file.db ".backup backup.db"`.

Restore: stop Studio → copy backup over the live path → restart → verify
`GET /ready` and `GET /api/v1/audit/verify` (`chain_valid: true`).

Retention: keep daily snapshots ≥7 days; the audit ledger is the forensic
record — back it up first and most often.

## 4. Health, logs & observability (S5)

- `GET /health` — process up. `GET /ready` — dependencies reachable.
- `X-Request-ID` on every response; send `X-Request-ID: <id>` to correlate
  client calls. Audit events carry `seq` + `event_hash` chain —
  `GET /api/v1/audit/verify` proves ledger integrity (tamper-evidence over
  recorded events, not execution proof).
- Structured request logging beyond the request-ID middleware is
  platform-side (reverse proxy / log drain); the app emits uvicorn access
  logs to stdout/stderr.

## 5. Rollback

Code rollback = redeploy previous pinned commit (`TAAS_COMMIT`-style pinning
is the supported pattern; notebooks pin immutable SHAs). Data is
forward-compatible only within the same schema version — before rolling
back across a schema change, restore the matching backup set.

## 6. Incident handling

| Symptom | First checks |
|---|---|
| All API calls 401 | Credential revoked/expired; `GET /admin/api-keys` with a valid key |
| All API calls 503 | No credential source configured — set token or create a key |
| Sign/approve 503 | `TAAS_EVIDENCE_ATTESTATION_KEY` unset |
| MCP inspect fails | Server command in `TAAS_MCP_SERVERS_*` must be stdio on the API host; Studio never runs browser-supplied commands |
| Suspected tampering | `GET /api/v1/audit/verify` → `first_divergence` identifies the seq; restore from last good backup |
| Disk full | SQLite stores grow with audit/events/runs; check `TAAS_*_PATH` volumes |

## 7. Explicit non-goals (do not "fix" these)

- Studio never invokes MCP tools (`tools/call` is not implemented anywhere).
- Discovery/evidence/audit records are observations — never execution,
  authorization, or claim-truth proof.
- No tenant isolation, no `eval/*`, no governed execution sandbox.
