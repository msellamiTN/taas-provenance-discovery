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

## 2. UX surface → activity mapping

### A1 · Define intent

| Surface | Role |
|---|---|
| Objective Engineering (`#agent-goal-panel`, UX-2) | Intent → GoalSpec decomposition, model proposal (proposal only) |
| Objective Traceability Explorer (UX-9) | Model-assisted `objectives/prepare`, clause→goal→outcome projection |
| GoalSpec designer (`#goal-editor`, UX-5) | Visual goals, deps, classes, Θ vocabulary drawer, policy presets |
| Agent Engineering (`#agent-engineering-workspace`) | `agents/decompose` assisted authoring |

### A2 · Build & configure capabilities

| Surface | Role |
|---|---|
| Agent registry manifest workspace (`#agent-manifest…`) | Register/validate/publish immutable Agent versions |
| Skill Lifecycle & Version Control (UX-14) | Skill versions, signatures, revocation |
| Model catalog + runtime (`#models`, `#model-runtime-panel`) | Unverified metadata; load/status (no sandboxed inference claims) |
| Model inference sandbox (`#agent-chat-panel`) | Chat completions where a model is loaded — labeled runtime sandbox |
| Workspace drafts (`/api/v1/workspaces` UI) | Durable draft save/restore; restore invalidates review |

### A3 · Discover & compose tools

| Surface | Role |
|---|---|
| Tool registry (`#bench-tools`, UX-3) | Browse, filter, basket, inspector w/ Core identity + capability intelligence |
| Tool Registry & MCP Governance (UX-15) | Retained identities, MCP servers, content-addressed snapshots |
| Tool discovery (`#discovery`) | Core engine run; certificate; reproducibility envelope |
| Tool Selection & Eligibility (UX-16) | retrieve → eligibility → compare; RRF relevance ≠ authorization |
| Discovery Selection & Composition (UX-23) | Persisted-run observation; demo/live separation |
| Hypergraph explorer | Reachability/projection views |
| MCP connections (`#mcp-studio`) | Server inventory + inspect (tools/list only, no tools/call) |

### A4 · Verify trust & compliance

| Surface | Role |
|---|---|
| Assurance center (`#certificate-panel`) | Certificate S/C/P/E/L/V + M/B diagnostics, counterexamples |
| Agent Governance & Trust Center (UX-24) | Exact-version posture: verdict/readiness/approvals/events/audit |
| Release Center (UX-10) | Readiness verdicts + approvals ledger + preflight boundary |
| Governance Policy Designer (UX-17) | Subject+facts → `policy/evaluate` verdict (diagnostic only) |
| Policy Testing & Simulation (UX-18) | Client-side scenario suites, MATCH/MISMATCH/ERROR, nothing persisted |
| Compliance & Assurance Dashboard (UX-20) | Demo/live separation; live = audit observations only |
| Risk & Remediation Workbench (UX-21) | Same separation; no risk-register API → unavailable |
| Evidence & Provenance Inspector (UX-12) | Content-addressed evidence verify, fail closed |
| Evidence explorer / diff & impact (UX-6) | Evidence records + change impact |
| Platform Governance & Quality (UX-8) | Quality posture, governance APIs tab, agents picker |

### A5 · Operate, observe & audit

| Surface | Role |
|---|---|
| Runtime & Observability (UX-7) | Host/hardware/model diagnostics — observations not execution |
| Operations Command Center (UX-11) | 4-endpoint ops view + source retrieval log |
| Agent Lifecycle & Version Control (UX-13) | Registry inventory, lifecycle states |
| Agent Observability (UX-22) | Agents/events/runs/runtime — bounded, demo/live |
| Governance Audit Timeline (UX-19) | `audit/events` + `audit/verify`, hash chain, evidence links |
| Discovery history & audit (`#discovery-observability`) | Persisted runs inspector |
| Runtime diagnostics (`#runtime-overview`) | Process/GPU probe |

### A6 · Evaluate results & manage platform

| Surface | Role |
|---|---|
| Benchmark workspace / task browser (`#workspace`) | Dataset counts, task selection → GoalSpec seed |
| Platform overview / settings | Health/readiness, token, connection state |
| Deferred: evaluator UX | `eval/*` deliberately absent — separate security project, gold-label isolation |

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
| A5 Operate | No per-agent operational metrics | Open — UX-22 correctly reports unavailable; needs real runtime telemetry source |
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
7. ~~**A1 templates**~~ — **done** (`4964cec`): versioned GoalSpec template catalog; every draft round-trips `/goals/validate`.
8. **Deferred** — evaluator (`eval/*`), production auth, execution sandbox: separate security projects per MEGAPLAN §6; do not build in this lane.
