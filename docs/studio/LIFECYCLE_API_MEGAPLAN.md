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

| Activity | Gaps worth filing |
|---|---|
| A1 Define | Server-side proposal provenance (who edited which goal field); versioned GoalSpec templates |
| A2 Build | Agent version diff endpoint; manifest signature/attestation parity with skills (skills have sign/revoke, agents don't) |
| A3 Discover | `GET /tools` lacks category/source facet counts for faceted search; no run-diff endpoint (`runs/a vs runs/b`) |
| A4 Verify | No persisted policy-verdict history (UX-18 suites are session-only by design); no evidence freshness batch query |
| A5 Operate | No per-agent operational metrics (UX-22 marks them unavailable — correct today); audit events bounded to 1,000 oldest-first, no cursor |
| A6 Evaluate | Everything in §3-A6 — deferred, not gaps |

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

1. **Nav regroup** — reorder `<nav>` links only; zero functional change; nav test already scoped to `<nav>`.
2. **Group headers + boundary copy** — activity eyebrow labels per section (rename "GOVERN · ASSURE" etc. to activity names); tests pin specific ids, not eyebrow text.
3. **A2 parity** — Agent manifest sign/attest endpoints mirroring skills (Core work, needs owner decision).
4. **A3 facets** — `/tools?facets=` for UX-15 faceted search (Core + UX slice).
5. **A5 cursor** — audit events pagination cursor (Core).
6. **Deferred** — evaluator (`eval/*`), production auth, execution sandbox: separate security projects per MEGAPLAN §6; do not build in this lane.
