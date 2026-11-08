# TaaS Studio — Agent Lifecycle Megaplan (Core API × UX/D)

Status: analysis + target grouping for `devin/studio-ux-integration-v1` @ `ac14b7b`.
Supersedes the UX-N numbering as the organizing frame; UX identifiers remain
implementation increments, not product structure.

## 1. Organizing principle

The product is organized around the **lifecycle of an AI Agent and its tools**,
not the chronological sequence UX-2 … UX-24. An operator moves through six
connected activities:

| # | Activity | Question the operator asks |
|---|----------|---------------------------|
| A1 | Define | What must the Agent / AI system accomplish? |
| A2 | Build | How are its capabilities configured? |
| A3 | Discover | Which tools and skills compose the solution? |
| A4 | Verify | Is the proposed configuration trustworthy and compliant? |
| A5 | Operate | What does the running lifecycle look like (observe + audit)? |
| A6 | Evaluate & Manage | How do results, releases and the platform itself get governed? |

Boundary invariant preserved throughout: **proposal ≠ evidence ≠ authorization
≠ execution**. No surface may imply execution occurred; approval does not grant
authorization; preflight does not execute; diagnostics are observations.

## 2. UX surface → activity mapping (shared coordination map)

**Lane ownership.** Devin = Core API, schemas, registries, evidence, policy,
audit, Hypergraph (this table's *API contract* column). Codex = UX surfaces,
mockups, API integration, demo experience (the *Demo state* column is
co-authored: Devin seeds it, Codex maintains per-surface scenario docs). Contract
= this table; neither lane duplicates the other's implementation. UX-xx labels
are internal traceability only — never user-facing.

Demo states: `live-only` (real Core data, no synthetic) · `demo/live split`
(explicit `DEMO DATA · ILLUSTRATIVE` vs `LIVE CORE` modes) · `demo-only`
(no live source — must not imply real data) · `pending` (scenario not yet authored).

### A1 · Define intent

| Surface | Feature | API contract | Demo state |
|---|---|---|---|
| Objective Engineering (`#agent-goal-panel`, UX-2) | Intent → GoalSpec decomposition; model proposal is proposal-only | `POST /objectives/discover`, `POST /objectives/prepare`, `POST /goals/validate` | live-only |
| Objective Traceability Explorer (UX-9) | Clause→goal→outcome projection via Hypergraph | `POST /objectives/prepare`, `GET /hypergraph/objective-traceability` | live-only |
| GoalSpec designer (`#goal-editor`, UX-5) | Visual goals/deps/classes, Θ drawer, policy presets, template catalog | `POST /goals/validate`, `GET /goalspec/templates`, `GET /goalspec/templates/{id}`, `GET /reference/vocabulary` | live-only — catalog consumed end-to-end (verified); templates authored, not validated on load |
| Agent Engineering (`#agent-engineering-workspace`) | `agents/decompose` assisted authoring | `POST /agents/decompose`, `POST /agents/validate`, `POST /goals/validate` | live-only |

### A2 · Build & configure capabilities

| Surface | Feature | API contract | Demo state |
|---|---|---|---|
| Agent lifecycle & versions (`#agent-lifecycle-center`, UX-13) | Register/validate/publish immutable versions, sign/revoke, diff, events | `POST/GET /agents`, `GET …/versions/{v}`, `POST …/validate`, `POST …/publish`, `GET …/diff/{b}`, `POST/GET …/sign(ature)`, `POST/GET …/revoke(ation)`, `GET /agents/events` | live-only |
| Skill lifecycle & versions (UX-14) | Skill versions, signatures, revocation, dependency DAG | `POST/GET /skills`, `…/validate`, `…/publish`, `…/sign(ature)`, `…/revoke(ation)`, `GET /skills/events`, `GET …/dependency-graph` | live-only |
| Model catalog + runtime (`#models`, `#model-runtime-panel`) | Unverified metadata; load/status | `GET /models/search`, `/models/detail`, `/models/artifacts`, `POST /models/estimate-memory`, `POST /models/load`, `GET /models/runtime` | live-only (metadata unverified by design) |
| Model inference sandbox (`#agent-chat-panel`) | Chat completions where a model is loaded — labeled runtime sandbox | `POST /models/chat` | live-only, sandbox-scoped |
| Workspace drafts | Durable draft save/restore; revision provenance | `GET/POST/PUT/DELETE /workspaces`, `GET /workspaces/{id}/revisions` | live-only |

### A3 · Discover & compose tools

| Surface | Feature | API contract | Demo state |
|---|---|---|---|
| Tool registry (`#bench-tools`, UX-3) | Browse, filter, basket, inspector + capability intelligence | `GET /tools`, `GET /tools?category=`, `GET /tools/{server}/{name}`, `GET /tools/{server}/{name}/intelligence` | live-only |
| Registry & MCP governance (UX-15) | Facet filters, retained identities, snapshots | `GET /tools` (`facets` block), `GET /mcp/servers`, `GET /mcp/servers/{id}/inspect`, `GET /mcp/registry/snapshots*` | live-only |
| Tool discovery (`#discovery`) | Core engine run, certificate, reproducibility envelope | `POST /discover`, `GET /discovery/runs`, `GET /discovery/runs/{id}` | live-only |
| Discovery review gate (UX-25) | Client-side pre-run review dialog: GoalSpec/toolset/policy summary, exact JSON preview, readiness checks, explicit ack | none — review gate on the existing `POST /discover` submit path; Core contract unchanged | live-only (verified) |
| Selection & eligibility (UX-16) | retrieve → eligibility → compare; RRF ≠ authorization | `POST /tools/retrieve`, `POST /tools/eligibility`, `POST /tools/compare` | live-only |
| Discovery & composition (UX-23) | Persisted-run observation; demo/live separation | `GET /discovery/runs`, `GET /discovery/runs/{id}`, `GET /discovery/runs/{a}/diff/{b}` | demo/live split (verified) |
| Hypergraph explorer | Reachability/projection views | `GET /hypergraph/skills/{id}/versions/{v}`, `GET /hypergraph/objective-traceability` | live-only |
| MCP connections (`#mcp-studio`) | Server inventory + inspect; tools/list only, no tools/call | `GET /mcp/servers`, `GET /mcp/servers/{id}/inspect`, `GET /mcp/registry/snapshots`, `POST /mcp/registry/snapshots/inspect` | live-only (invocation disabled by design) |

### A4 · Verify trust & compliance

| Surface | Feature | API contract | Demo state |
|---|---|---|---|
| Assurance center (`#certificate-panel`) | Certificate S/C/P/E/L/V + M/B diagnostics, counterexamples | `GET /assurance/evidence/{id}`, `POST /assurance/evidence/freshness` | live-only |
| Trust center (UX-24) | Exact-version posture: verdict/readiness/approvals/events/audit | `GET …/policy-verdict(+history)`, `GET …/release-readiness`, `GET …/approvals`, `GET /agents/events`, `GET /audit/verify` | live-only |
| Release Center (UX-10) | Readiness verdicts + approvals + preflight boundary | `GET …/release-readiness`, `GET/POST …/approvals`, `POST …/authorization/preflight` | live-only |
| Policy designer (UX-17) | Subject+facts → verdict (diagnostic only) | `POST /policy/evaluate` | live-only |
| Policy testing (UX-18) | Client-side scenario suites; nothing persisted | `POST /policy/evaluate` (per-case) | live-only |
| Compliance dashboard (UX-20) | Demo/live separation; live = audit observations only | `GET /audit/events`, `GET /audit/verify` | demo/live split (verified) |
| Risk & remediation (UX-21) | Same separation; no risk-register API → unavailable | `GET /audit/events`, `GET /audit/verify` | demo/live split (verified) |
| Evidence inspector (UX-12) | Content-addressed verify, fail closed | `GET /assurance/evidence/{id}` | live-only |
| Evidence explorer / diff & impact (UX-6) | Evidence records + change impact | `GET /assurance/evidence/{id}`, `POST /assurance/evidence/freshness` | live-only |
| Governance & quality (UX-8) | Quality posture, governance APIs tab, agents picker | `GET /agents`, `GET /audit/events` | live-only |

### A5 · Operate, observe & audit

| Surface | Feature | API contract | Demo state |
|---|---|---|---|
| Runtime & observability (UX-7) | Host/hardware/model diagnostics — observations not execution | `GET /runtime/status`, `GET /runtime/hardware`, `GET /models/runtime` | live-only |
| Operations Command Center (UX-11) | 4-endpoint ops view + source retrieval log | `GET /runtime/status`, `GET /discovery/runs`, `GET /audit/verify`, `GET /agents` | live-only |
| Agent lifecycle & version control (UX-13) | Registry inventory, lifecycle states | `GET /agents`, `GET /agents/events` | live-only |
| Agent observability (UX-22) | Agents/events/runs/runtime — bounded, demo/live | `GET /agents`, `GET /agents/events`, `GET /discovery/runs`, `GET /runtime/*`, **NEW** `GET /agents/{id}/versions/{v}/activity` | demo/live split (verified end-to-end, `2470afb`) |
| Audit timeline (UX-19) | `audit/events` cursor paging + `audit/verify`, evidence links | `GET /audit/events?after_seq=`, `GET /audit/verify` | live-only |
| Workspace Revision History (UX-26) | Immutable saved-draft history, actor/digest, field-level diff and explicit completeness | `GET /workspaces/{id}/revisions` (`taas.workspace-revision-history/v1`) | live-only · read-only |
| Discovery history & audit (`#discovery-observability`) | Persisted runs inspector | `GET /discovery/runs`, `GET /discovery/runs/{id}` | live-only |
| Runtime diagnostics (`#runtime`) | Process/GPU probe | `GET /runtime/status`, `GET /runtime/hardware` | live-only |

### A6 · Evaluate results & manage platform

| Surface | Feature | API contract | Demo state |
|---|---|---|---|
| Benchmark workspace / task browser (`#workspace`) | Dataset counts, task selection → GoalSpec seed | `GET /bench/datasets`, `GET /bench/tasks`, `GET /bench/tools` | live-only |
| Platform overview / settings (`#overview-workspace`) | Health/readiness, token, connection state | `GET /health`, `GET /ready` | live-only |
| Deferred: evaluator UX | `eval/*` deliberately absent — separate security project, gold-label isolation | — | unavailable by design |

## 3. Core API → activity mapping (68 routes)

### A1 · Define — covered

`POST /objectives/prepare` · `POST /objectives/discover` · `POST /agents/decompose` · `POST /goals/validate` · `GET /reference/vocabulary`

### A2 · Build — covered

`POST /agents` · `GET /agents` · `GET /agents/{id}/versions/{v}` · `POST …/validate` · `POST …/publish` · `POST /skills` (+validate/publish/sign/revoke) · `GET /skills` (+events/version/signature/revocation) · `GET/POST/PUT/DELETE /workspaces` · `GET /models/*` · `POST /models/load` · `POST /models/chat` · `POST /models/estimate-memory`

### A3 · Discover — covered

`GET /tools` · `GET /tools/{server}/{name}` (+`/intelligence`) · `POST /tools/retrieve` · `POST /tools/eligibility` · `POST /tools/compare` · `POST /discover` · `GET /discovery/runs` (+`/{run_id}`) · `GET /mcp/servers` · `GET /mcp/registry/snapshots*` · `POST /mcp/*/inspect` · `GET /bench/*` · `POST /agents/validate`

### A4 · Verify — covered

`POST /policy/evaluate` · `GET …/policy-verdict` · `GET …/release-readiness` · `GET/POST …/approvals` · `POST …/authorization/preflight` · `GET /skills/{id}/versions/{v}/signature|revocation` · assurance evidence routes (`build_assurance_router`)

### A5 · Operate — covered

`GET /runtime/status` · `GET /runtime/hardware` · `GET /models/runtime` · `GET /audit/events` · `GET /audit/verify` · `GET /agents/events` · `GET /skills/events` · `GET /health` · `GET /ready`

### A6 · Evaluate & manage — partial / intentionally absent

| Route area | State |
|---|---|
| `/api/v1/eval/*` | **Absent by design** — evaluator is a separate security project; gold labels must stay isolated from discovery/analyst paths |
| Platform admin (users, quotas, tenants) | Absent — production hardening phase (OIDC, RBAC, rate limits) |
| Execution (`invoke`, `tools/call`, workers) | **Absent by design** — requires sandbox/credential isolation project |

## 4. API gap analysis per activity

| Activity | Gaps worth filing | Status |
|---|---|---|
| A1 Define | Server-side proposal provenance (who edited which field) | **Delivered** — `GET /workspaces/{id}/revisions` (`taas.workspace-revision-history/v1`): immutable per-revision actor + added/removed/changed JSON paths, cascade-deleted with the draft |
| A1 Define | Versioned GoalSpec templates | **Delivered** — `GET /goalspec/templates` + `GET /goalspec/templates/{id}` (`taas.goalspec-template(-list)/v1`): curated immutable catalog, `spec_sha256` per draft, every draft passes `/goals/validate`; explicit `authored_draft_not_validation_not_authorization` semantics |
| A2 Build | Agent version diff endpoint | **Delivered** — `GET /agents/{id}/versions/{a}/diff/{b}` (`taas.agent-version-diff/v1`) |
| A2 Build | Manifest signature/attestation parity with skills | **Delivered** — `POST/GET …/sign`, `…/signature`, `POST/GET …/revoke`, `…/revocation`; revoked versions refuse new signatures |
| A3 Discover | `GET /tools` lacks category/source facet counts | **Delivered** — deterministic `facets` over the filtered result set |
| A3 Discover | No run-diff endpoint | **Delivered** — `GET /discovery/runs/{a}/diff/{b}` (`taas.discovery-run-diff/v1`) |
| A4 Verify | No persisted policy-verdict history | **Delivered** — agent-scoped verdicts append `policy_verdict` ledger events; `GET …/policy-verdict/history` |
| A4 Verify | No evidence freshness batch query | **Delivered** — `POST /assurance/evidence/freshness` (`taas.evidence-freshness/v1`, fail-closed per binding) |
| A5 Operate | Audit events bounded to 1,000 oldest-first, no cursor | **Delivered** — `after_seq` keyset pagination with `has_more`/`next_cursor` |
| A5 Operate | `audit/verify` scanned only the first 1,000 events | **Delivered** — full-ledger scan in bounded batches, `scan_scope: full_ledger` |
| A5 Operate | No per-agent operational metrics | **Delivered (recorded activity)** — `GET /agents/{id}/versions/{v}/activity` (`taas.agent-version-activity/v1`): version-scoped lifecycle events, verdict/approval audit counts, verified human_approval evidence, revocation, manifest facts; performance telemetry stays on the explicit `unsupported_metrics` list until governed execution/telemetry exists |
| A2 Build | `/agents/events` lacks `version` param | **Delivered** — `GET /agents/events?agent_id=&version=&limit=`; exact-match on the persisted per-event column, newest-first |
| A2 Build | `/skills/events` lacks `version` param | **Delivered** — `GET /skills/events?skill_id=&version=&limit=`; same exact-match semantics as agents |
| A2 Build | No skill version-diff endpoint | **Delivered** — `GET /skills/{id}/versions/{a}/diff/{b}` (`taas.skill-version-diff/v1`): `manifest_sha256`/`lifecycle_state` a/b, `changes` {added/removed/changed `{path,a,b}`/truncated}, `record_semantics: structural_diff_of_persisted_manifests_not_behavior_evidence`, `execution_record: false` |
| A2 Build | No skill recorded-activity endpoint | **Delivered** — `GET /skills/{id}/versions/{v}/activity` (`taas.skill-version-activity/v1`): version-scoped lifecycle events, verified `publisher_signature` count, revocation record, manifest-derived configuration facts; per-source `state: recorded\|unavailable`; `unsupported_metrics` + `unavailable_reason` (no governed execution/telemetry) |
| A3 Discover | No registry snapshot diff | **Delivered** — `GET /mcp/registry/snapshots/{a}/diff/{b}` (`taas.mcp-snapshot-diff/v1`): snapshots normalized into `server_id`/`tool.name`-keyed maps (collision-safe) so paths are semantic — `servers.docs.tools.search.desc`; server/tool counts + `record_semantics: structural_diff_of_captured_registry_schemas_not_tool_behavior_evidence` |
| A5 Operate | `/audit/events` not subject-scoped | **Delivered** — `subject_agent_id` + `subject_version` query params (exact-match on `subject_json` keys, combinable with `event_type` + `after_seq` cursor; missing keys never match) |
| A2 Build | Revisions server-side filters | **Conditional** — `GET /workspaces/{id}/revisions?kind=&actor=` + cursor only if the re-approved UX-26 mockup requires server-side filtering/pagination (client-side over `limit=500` may suffice) |
| A6 Evaluate | Everything in §3-A6 | Deferred, not gaps |

## 5. Navigation target (UX/D)

Regroup the left rail from BUILD / TOOLS & DISCOVERY / OPERATE into the six
activities; keep workspace content unchanged (labels map 1:1 above):

1. **DEFINE** — Objective Engineering · Agent Engineering · GoalSpec designer · Traceability explorer
2. **BUILD** — Agent manifest/versions · Skill lifecycle · Models & runtime · Workspace drafts
3. **DISCOVER** — Tool registry (UX-3) · Registry & MCP governance (UX-15) · Discovery · Selection workbench (UX-16) · Composition (UX-23) · Hypergraph · MCP connections
4. **VERIFY** — Assurance center · Trust center (UX-24) · Release Center (UX-10) · Policy designer (UX-17) · Policy testing (UX-18) · Compliance (UX-20) · Remediation (UX-21) · Evidence inspector (UX-12) · Governance & quality (UX-8)
5. **OPERATE** — Runtime & observability (UX-7) · Ops command center (UX-11) · Agent lifecycle (UX-13) · Agent observability (UX-22) · Audit timeline (UX-19) · Discovery history
6. **EVALUATE & MANAGE** — Benchmark workspace · Platform overview · (evaluator placeholder, visibly unavailable until the security project lands)

Acceptance: every nav link resolves; no UX-N numbers in user-facing labels;
each group header carries the boundary line ("no authorization or execution
occurs in this activity" where applicable).

## 6. Execution order (bottom-up, green each step)

1. ~~**Nav regroup**~~ — **done** (`c92d3cc`): six activity groups, all links verified.
2. ~~**Group headers + boundary copy**~~ — **done** (`4429cd6`): activity eyebrow labels via dynamic nav-label derivation + per-activity boundary hints; tests pin ids.
3. ~~**A2 parity**~~ — **done**: agent sign/signature/revoke/revocation mirror skills; revoked versions refuse signatures.
4. ~~**A3 facets**~~ — **done**: `facets` block on `/api/v1/tools`; UX-15 consumption is a follow-on slice.
5. ~~**A5 cursor**~~ — **done**: `after_seq` keyset pagination; verify walks the full ledger.
6. ~~**A1 provenance**~~ — **done** (`3bf8584`): immutable per-revision workspace edit history with field-level added/removed/changed paths + actor.
11. **UX-26** — Workspace Revision History browser surface: read-only inspection of the existing A1 provenance API; no Core contract changes.
7. ~~**A1 templates**~~ — **done** (`4964cec`): versioned GoalSpec template catalog; every draft round-trips `/goals/validate`.
8. ~~**Registry lifecycle hardening**~~ — **done** (`20da92c`): engine-level transition validation + event-consistency + updated_at guards on agent/skill registries.
9. ~~**A5 recorded activity**~~ — **done** (`d32c9f6` + `e32ae88`): `GET /agents/{id}/versions/{v}/activity`, explicit `state: recorded|unavailable` per source block; UX-22 consumes end-to-end (verified `2470afb`).
10. **Deferred** — evaluator (`eval/*`), production auth, execution sandbox: separate security projects per MEGAPLAN §6; do not build in this lane.
