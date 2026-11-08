# TaaS Studio — Global UX and Functional Convergence Audit

**Audit branch:** devin/studio-convergence  
**Audit date:** 2026-11-08  
**Status:** Initial repository source audit. Browser acceptance and full runtime validation are not claimed.

## 1. Executive finding

TaaS Studio contains substantial functionality, but it is not yet one coherent, fully validated product experience. The central gap is between a broad Core API surface, a large single-document frontend, multiple generations of UX documentation, independently developed feature branches, and incomplete end-to-end acceptance.

The convergence effort must address product coherence, API contract fidelity, engineering quality, and delivery traceability together. Route existence or a rendered screen is not proof of a complete or production-ready feature.

## 2. Audited source baseline

Fetched from branch devin/studio-convergence:

| Artifact | Repository path | Observed blob SHA | Size |
|---|---|---|---:|
| Studio frontend | src/taas/studio/static/index.html | 546c25b0d9e145fad1236411ee1ce04e11132c7a | 320,452 characters |
| Studio API | src/taas/studio/api.py | b422cb532cf8c81d718238c26190aef8ecc0a487 | 122,310 characters |
| Product UX blueprint | docs/studio/PRODUCT_UX_BLUEPRINT.md | f61de4c213af437df2fa5f4b543b3be5120620fe | 12,719 characters |
| Feature catalog | docs/studio/FEATURE_CATALOG.md | c1da24f36bd73b58b21261d897d1caccb5f59bd1 | 14,265 characters |

Static source extraction found 34 unique HTML section IDs and 62 route decorators in api.py (35 GET, 27 POST). The application also mounts a separate assurance router, which adds GET /api/v1/assurance/evidence/{evidence_id}; therefore the inspected API surface contains at least 63 effective route paths (36 GET, 27 POST). These are source counts, not test or runtime counts.

The frontend remains a single HTML document with embedded CSS and JavaScript. The API remains a large FastAPI module importing multiple domain services. Both need incremental modularization with behavior-preserving tests, not a wholesale rewrite.

## 3. Target product domains

### A. Command Center
Platform overview, service readiness, workspace entry/context, supported recent activity, global navigation and shortcuts.

### B. Build & Engineer
Objective Engineering, GoalSpec Designer, Agent Engineering, Model Catalog and Runtime configuration, Skill Registry and dependency management, Tool Registry and MCP contract inspection.

### C. Discover & Compose
Tool Intelligence, retrieval, eligibility, comparison, goal/tool alignment, discovery and abstention, Hypergraph Explorer and composition views.

### D. Assure & Govern
Certificate/assurance center, Evidence Explorer, Evidence Diff & Impact, Platform Governance & Quality, Objective Traceability, Agent Governance & Trust Center, policy, approvals, authorization preflight and release readiness where backed by Core contracts.

### E. Operate & Observe
Runtime diagnostics, model inference/runtime status, Agent lifecycle, Runtime & Observability, Discovery History, audit verification, Agent/Skill lifecycle events.

### F. Evaluate & Improve
Benchmark workspace, dataset/task browsing, experiment workbench, evaluation results, reproducibility and reports.

### G. Global Administration
API connection/authentication, data sources, registry snapshots, model/profile configuration, user and workspace preferences.

This domain mapping organizes existing features; it does not rename or erase historical UX identifiers.

## 4. Verified API route inventory

Static extraction from src/taas/studio/api.py found:

**Health/runtime and Studio shell**
- GET /
- GET /health
- GET /ready
- GET /api/v1/runtime/hardware
- GET /api/v1/runtime/status

**Goal/objective**
- POST /api/v1/goals/validate
- POST /api/v1/objectives/prepare
- POST /api/v1/objectives/discover
- POST /api/v1/hypergraph/objective-traceability

**Discovery/history**
- POST /api/v1/discover
- GET /api/v1/discovery/runs
- GET /api/v1/discovery/runs/{run_id}

**Benchmark/tool registry**
- GET /api/v1/bench/datasets
- GET /api/v1/bench/tasks
- GET /api/v1/bench/tools
- GET /api/v1/tools
- GET /api/v1/tools/{server}/{name}
- GET /api/v1/tools/{server}/{name}/intelligence
- POST /api/v1/tools/retrieve
- POST /api/v1/tools/eligibility
- POST /api/v1/tools/compare

**MCP registry**
- GET /api/v1/mcp/servers
- POST /api/v1/mcp/servers/{server_id}/inspect
- GET /api/v1/mcp/registry/snapshots
- GET /api/v1/mcp/registry/snapshots/{snapshot_id}
- POST /api/v1/mcp/registry/snapshots/inspect

**Models/inference**
- GET /api/v1/models/search
- GET /api/v1/models/detail
- GET /api/v1/models/artifacts
- GET /api/v1/models/runtime
- POST /api/v1/models/estimate-memory
- POST /api/v1/models/load
- POST /api/v1/models/chat

**Agents**
- GET /api/v1/agents
- GET /api/v1/agents/events
- GET /api/v1/agents/{agent_id}/versions/{version}
- POST /api/v1/agents
- POST /api/v1/agents/decompose
- POST /api/v1/agents/validate
- POST /api/v1/agents/{agent_id}/versions/{version}/validate
- POST /api/v1/agents/{agent_id}/versions/{version}/publish
- GET /api/v1/agents/{agent_id}/versions/{version}/release-readiness
- GET /api/v1/agents/{agent_id}/versions/{version}/policy-verdict
- GET /api/v1/agents/{agent_id}/versions/{version}/approvals
- POST /api/v1/agents/{agent_id}/versions/{version}/approvals
- POST /api/v1/agents/{agent_id}/versions/{version}/authorization/preflight

**Skills**
- GET /api/v1/skills
- GET /api/v1/skills/events
- POST /api/v1/skills
- POST /api/v1/skills/validate
- GET /api/v1/skills/{skill_id}/versions/{version}
- POST /api/v1/skills/{skill_id}/versions/{version}/validate
- POST /api/v1/skills/{skill_id}/versions/{version}/publish
- POST /api/v1/skills/{skill_id}/versions/{version}/sign
- GET /api/v1/skills/{skill_id}/versions/{version}/signature
- POST /api/v1/skills/{skill_id}/versions/{version}/revoke
- GET /api/v1/skills/{skill_id}/versions/{version}/revocation
- GET /api/v1/skills/{skill_id}/versions/{version}/dependency-graph
- GET /api/v1/hypergraph/skills/{skill_id}/versions/{version}

**Policy/evidence/audit**
- POST /api/v1/policy/evaluate
- GET /api/v1/assurance/evidence/{evidence_id}
- GET /api/v1/audit/events
- GET /api/v1/audit/verify

The assurance evidence route is defined in the separately mounted src/taas/studio/assurance_routes.py router, not directly in api.py. Route existence does not prove frontend integration, production authorization, safe operational readiness, or correct UI semantics. Each route needs request/response schema, auth, side-effect, error, pagination, provenance and state-semantics review before being exposed as an action.



### Route protection and POST side-effect classification

The inspected app declares 62 routes (35 GET, 27 POST). The separately mounted assurance router adds one authenticated GET route. In the inspected source, the three public routes are GET /health, GET /ready and GET /; the remaining 60 effective routes declare the bearer-token dependency. This confirms a route-level token boundary, not a production identity/role/tenant authorization model.

POST routes must not be treated as one generic “action” class:

| Operation class | Routes / behavior | UX treatment |
|---|---|---|
| Pure validation/estimation | GoalSpec validation, Agent/Skill manifest validation, model-memory estimate | Safe to present as explicit validation/estimate; do not imply semantic correctness or measured capacity |
| Discovery analysis | Tool retrieve, eligibility, comparison, discovery | Explicit user-triggered analysis; discovery persists a run/audit record, requires human_review_confirmed, and does not invoke MCP tools |
| Model inference/runtime | Model load and model chat; Agent decomposition uses a selected model to propose a GoalSpec | Clearly label model download/load and inference; never label these as MCP execution |
| Registry mutations | Agent/Skill draft creation, saved-version validation transitions, publish, Skill signing/revocation | Require explicit user intent, exact immutable subject/version, precondition display, confirmation, and audit/provenance feedback |
| Human approval evidence | Agent approval-record endpoint | Explicit human action only; immutable evidence record, not authorization or execution permission |
| MCP metadata inspection | Server inspect and registry snapshot inspect | Read-only tools/list inspection only; snapshot inspection also persists an immutable registry snapshot, so disclose this state change |
| Governance diagnostics | Policy evaluation and authorization preflight | Diagnostic decision only; caller-asserted facts must remain labelled, and preflight must never be presented as an authorization grant |

The discovery handler explicitly rejects requests without human_review_confirmed (HTTP 409), records a discovery run and audit event, and states that it does not invoke MCP tools. The authorization-preflight handler explicitly says it evaluates trusted preconditions only and never authorizes or invokes tools. The human-approval handler explicitly returns authorization_granted=false and execution_enabled=false.

## 5. Confirmed convergence defects and risks

| ID | Finding | Evidence | Required correction |
|---|---|---|---|
| C-01 | Feature catalog is stale | Catalog identifies feature/studio-goalspec-editor and commit e641fc7 as its audit baseline; it does not describe the current 62-route source | Rebuild from the actual integration target and classify every capability |
| C-02 | Blueprint and navigation are not reconciled | Blueprint specifies a persistent left rail/drawer; audited HTML uses a wrapping horizontal studio-nav | Prepare one shell mockup and implement only after comparing with approved designs |
| C-03 | Frontend is monolithic | 320,452-character index.html | Extract reusable modules incrementally with behavior-preserving tests |
| C-04 | API boundary is concentrated | 122,310-character api.py with 62 route declarations | Map routers/services/contracts and split safely by domain |
| C-05 | UX-24 is not on this audit branch | UX-24 exists on feature/ux-24-agent-governance-trust-center and draft PR #88 | Validate exact PR head, then integrate without losing approved work |
| C-06 | Documentation has multiple historical baselines | Blueprint, feature catalog and feature-specific docs describe different stages | Establish one source of truth and feature traceability |
| C-07 | API includes state-changing operations | Agent/Skill publish, approval, sign, revoke, model load/chat and authorization preflight POST routes exist | Classify side effects, permissions, confirmation and audit semantics |
| C-08 | Navigation mixes legacy and domain labels | HTML includes workspace labels and UX-number labels | Preserve identifiers in traceability; consolidate labels only through approved mockups |
| C-09 | Browser acceptance remains unproven | PR #88 records browser/keyboard and live Colab validation as pending | Add exact-head browser and Colab acceptance evidence |
| C-10 | Feature coverage is not proven by route counts | Static source extraction only | Build screen → endpoint → schema → test → acceptance matrix |\n| C-11 | UX-8 is currently an evidence-planning surface, not the governed policy workflow described in issue #87 | The HTML shows static NOT_RUN/UNKNOWN evidence tables; no calls to policy-verdict, release-readiness, approvals or authorization/preflight are present | Reconcile UX-8's approved scope with UX-24; implement only the already-approved workflow and keep unavailable evidence explicit |\n| C-12 | UX-24 adds read-only Agent trust views but deliberately omits authorization preflight | PR #88 uses version, readiness, policy verdict, approvals, Agent events and audit verification; it does not call authorization/preflight | Preserve the read-only UX-24 boundary; map any separately approved preflight view to the correct UX-8 workflow and label it diagnostic, never authorization |

## 6. Existing approved work and branch handling

- UX-7/UX-8/UX-9, F02, Evidence workspace and Release Center are covered by the approved implementation scope in issue #87. Do not restart mockup review for designs already approved.
- UX-24 is on feature/ux-24-agent-governance-trust-center and tracked by draft PR #88. Its documented automated suite passed 666 tests on code/test commit 1e69553aff3614d1aa934ca1f67927caf68c8170. A documentation-only follow-up exists at e2d26b94fa12e406d006975d063d4927d0547386. Browser/keyboard acceptance and live Colab validation remain pending.
- PR #88 has no submitted reviews or inline review threads at this audit.
- Preserve feature branches and accepted baselines until integration and validation evidence are reviewed. No merge or deployment is included in this audit.


## 7. Existing issue and PR traceability

| Tracker | Existing scope | Convergence treatment |
|---|---|---|
| Issue #63 | Design system and application shell | Reconcile target shell with current approved mockups; avoid a wholesale rewrite |
| Issue #64 | Platform overview dashboard | Verify every count/status against live Core data and real empty/error states |
| Issue #65 | Model, Agent, Skill, Tool and Assurance workspace integration | Use as the main cross-domain workflow integration anchor |
| Issue #66 | API-backed Hypergraph Explorer | Preserve Core-projected graph semantics and exact version/provenance |
| Issue #67 | Studio/Core API contract coordination | Require endpoint/schema/state/error/provenance contract before integration |
| Issue #87 | Approved UX-7/8/9, F02, Evidence and Release Center implementation scope | Treat prior mockup approvals as valid; close functional and acceptance gaps |
| PR #88 | UX-24 Agent Governance & Trust Center | Keep draft until browser/keyboard and exact-head Colab acceptance are complete |

The UX-24 branch comparison against the accepted M1 merge base 85594cd shows changes limited to three files: the Studio HTML (+94 lines), UX-24 tests (+97 lines), and UX-24 documentation (+73 lines). The API file is unchanged, consistent with UX-24 reusing existing Core endpoints. The convergence branch's changes relative to that same baseline are confined to this audit document.

## 8. Remediation workstreams

### W1 — Source of truth and traceability
Reconcile feature IDs, historical branch/PR ownership, implementation state and evidence. Resolve reused identifiers against repository history; never silently renumber.

### W2 — Product shell and navigation
Inventory screens, anchors, actions and routes. Map them to six domains. Prepare visual mockups for new/materially changed shell decisions, then implement after explicit approval.

### W3 — Shared interaction and design system
Standardize tokens and reusable components for tables, forms, detail panels, tabs, dialogs, status indicators and error boundaries. Implement loading, empty, partial, stale, denied, unavailable and error states. Validate keyboard/focus and responsive behavior.

### W4 — API contract and governance
Build endpoint inventory with schemas and side-effect classification. Verify auth for state-changing routes. Ensure read-only screens do not call write routes. Preserve approval ≠ authorization ≠ execution and discovery ≠ execution. Prevent secrets from entering browser logs, telemetry or exports.

### W5 — Domain workflow completion
Complete API-backed Build & Engineer, Discover & Compose, Assure & Govern, Operate & Observe, and Evaluate & Improve workflows. Keep model inference, Agent orchestration and MCP execution distinct. Keep evaluator ground truth isolated.

### W6 — Quality and acceptance
Add focused unit/API/frontend tests, negative governance tests, full regression, browser interaction, keyboard accessibility, responsive acceptance, exact-commit Colab validation where required, and linked artifacts.

## 9. Mandatory engineering rules

1. Preserve approved mockups and existing working behavior.
2. New UX follows mockup → explicit approval → implementation.
3. Never fabricate endpoints, metrics, evidence, telemetry, approvals or production state.
4. No implicit authorization or execution.
5. No new execute/invoke route in the current approved product scope.
6. Preserve human_review_confirmed where required by the Core discovery contract.
7. Separate model inference, Agent orchestration and MCP tool execution.
8. Do not expose evaluator ground truth to discovery/engineering.
9. Build → focused tests → full tests → browser/Colab acceptance → documentation.
10. No merge or deployment without explicit authorization.

## 10. First execution order

1. Complete feature-to-screen-to-route-to-test traceability.
2. Reconcile UX-24 with the convergence branch and validate exact-head CI.
3. Produce the global navigation/shell mockup using existing approved design decisions.
4. Fix contract and security mismatches before cosmetic refactoring.
5. Consolidate shared UI components and navigation incrementally.
6. Complete each domain workflow with API-backed acceptance evidence.

**Exit criterion:** every user-visible capability has a verified contract, accurate state model, working interactions, automated tests, documented limitations and acceptance evidence tied to an exact commit.
