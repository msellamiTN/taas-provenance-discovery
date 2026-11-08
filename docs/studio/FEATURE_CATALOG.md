# TaaS Studio — Verified Feature Catalog and UX Audit

Audit baseline: branch `devin/studio-ux-integration-v1`, commit `c3160b8754fa75201d2d58da81733661a7aac88a` (724 tests green). Earlier audit baselines: `e641fc7412dbb77ae44304562820db619aaf7359`, `a94d8e8`.

This catalog records what is present in the repository at the audit baseline. “Implemented” means a code/API surface exists; it does not imply production readiness or browser validation. No runtime invocation of MCP tools is provided by Studio.

## 1. Product boundary

TaaS Studio currently exposes an experimental, authenticated HTTP interface over the discovery core. Its responsibility is to author a GoalSpec, inspect retained capability metadata, compute a toolkit recommendation/abstention, and inspect pre-execution assurance evidence.

Four states must remain distinct:

1. **Intent** — the authored natural-language prompt and GoalSpec.
2. **Discovery** — candidate analysis and selected toolkit or abstention.
3. **Pre-execution assurance** — structural validation, certificate checks, provenance witnesses and counterexamples.
4. **Runtime outcome** — not implemented in this Studio API; no MCP tool is invoked by `POST /api/v1/discover`.

A selected toolkit is not proof that the task was semantically fulfilled. A valid certificate is not proof of runtime behavior. Structural GoalSpec validation does not establish that the authored contract faithfully represents the prompt.

## 2. API inventory

All endpoints below are implemented in `src/taas/studio/api.py`.

| Method and route | Authentication | Request | Response / behavior | Product state |
|---|---|---|---|---|
| `GET /health` | Public | None | Process health and service identifier | Implemented |
| `GET /ready` | Public | None | Readiness; requires configured API token; reports configured/uncalibrated profile | Implemented |
| `GET /api/v1/runtime/hardware` | Bearer | None | Host GPU/CUDA probe; does not load a model | Implemented; diagnostics only |
| `POST /api/v1/goals/validate` | Bearer | GoalSpec JSON | Structural contract checks and dependency topological order; `semantic_correctness_verified=false` | Implemented |
| `GET /api/v1/models/search` | Bearer | Query, limit, sort, pipeline tag | Bounded Hugging Face metadata search; no weight download | Implemented |
| `GET /api/v1/models/detail` | Bearer | Model repository ID | Safe model/config metadata | Implemented |
| `GET /api/v1/models/artifacts` | Bearer | Model repository ID | Artifact metadata and compatibility candidates; no download or execution | Implemented |
| `POST /api/v1/models/estimate-memory` | Bearer | Parameter count, quantization, optional architecture/KV-cache assumptions | Weight and optional KV-cache estimate | Implemented; estimate, not measured fit |
| `GET /api/v1/bench/datasets` | Bearer | None | Retained dataset catalogue, counts, source and local-data declaration | Implemented |
| `GET /api/v1/bench/tasks` | Bearer | Dataset, query, category, offset, limit | Prompt/task metadata; gold tool labels deliberately omitted | Implemented |
| `GET /api/v1/bench/tools` | Bearer | Source, query, limit, offset | Retained tool registry; annotations are untrusted declarations | Implemented |
| `POST /api/v1/discover` | Bearer | GoalSpec, 1–500 tools, policy, engine settings | Selected/abstained state, selected tools, canonical GoalSpec, gap, rho, certificate, counterexample, composition stats, duration, profile state, `execution_performed=false` | Implemented; discovery only |
| `GET /` | Public page | None | Serves the single-page Studio frontend | Implemented |

### API contract and trust notes

- The discovery endpoint validates the GoalSpec before invoking the discovery engine.
- The default model profile is explicitly uncalibrated and strict; unknown native capabilities remain unavailable rather than being guessed.
- Tool descriptions, schemas and annotations are input metadata. They must not be rendered as independently verified provenance.
- The benchmark task endpoint does not return `gold_tools` or `gold_unresolved`. Evaluation labels must remain in a separate evaluator boundary.
- The model catalog adapter is read-only metadata access. Artifact inspection does not download model weights or execute model repository code.
- The hardware endpoint reports host readiness; it does not establish that a particular model can be loaded or served.
- The discovery response's `status=selected` means a toolkit was selected by the engine. It does not mean benchmark success or semantic prompt satisfaction.
- The response's `gap` is the set of goals not delegated to the model under the core's terminology. It must not be casually described as “uncovered goals” without inspecting the corresponding witness/binding semantics.

## 3. Current browser experience

Frontend: `src/taas/studio/static/index.html` (single HTML document, inline CSS and JavaScript).

| Surface | Current behavior | Remaining UX work |
|---|---|---|
| Studio header and anchor navigation | Left-rail section navigation with grouped workspace links | No active route state, workspace identity or capability-aware navigation |
| Discovery workspace | Request configuration, result, reproducibility envelope and run-history deep link; durable draft save/restore via `/api/v1/workspaces` | No multi-draft workspace switching UI or review/confirmation step |
| Benchmark catalogue | Displays retained dataset counts/source | Add dataset snapshot/version identity and robust empty/error states |
| Task browser | Search, category, pagination, select task and copy prompt | No task provenance detail; imported task still requires human-authored semantic goals |
| Tool registry | Search/source filter, pagination, basket independent of filters, tool inspector with Core identity + capability intelligence; dedicated governance center (UX-15) | Trusted verification pipeline and registry version pinning |
| GoalSpec editor | Visual goal cards, prompt context types, add/remove, local checks, server validation, advanced JSON reload | Add dependency graph/table equivalence, type/effect reference catalogue, examples/templates, clearer field-level diagnostics |
| Request JSON | Advanced JSON payload editor + guided policy presets (read-only/egress-limited/strict-evidence) | Engine settings are not yet first-class guided editors |
| Discovery results | Status, metrics, selected toolkit, explanation and full response | Add explicit request/decision state taxonomy and candidate comparison |
| Assurance | Certificate mandatory/diagnostic checks, witnesses, goal binding/coverage and counterexample | Explain each check's formal meaning and evidence source/freshness; prevent green styling from implying task completion |
| Runtime diagnostics | Host/hardware/model observability workspace (UX-7) + operations command center (UX-11) | No runtime sessions, tool invocation, cancellation, logs or execution traces |
| Model catalog | Search and model metadata detail | No persisted model selection, benchmarked compatibility or deployment workflow |
| Model artifacts | Read-only artifact metadata and compatibility preflight | No weight download, sandboxed load test or inference |
| Memory estimate | Request-driven estimate API | UI currently needs explicit assumption transparency and measured-vs-estimated distinction |
| Experiments/evaluation | Research scripts and tests exist outside the Studio workflow | No integrated evaluator, run history, comparison dashboard or gold-label isolation UX |
| Settings | Token/API connection is represented in the page | No complete connection manager, profile management, audit settings or durable preferences |

Delivered Studio workspaces (all read-only / analysis-only, wired to real Core routes): UX-2 Objective Engineering, UX-3 Tool Registry, UX-5 GoalSpec designer, UX-7 runtime observability, UX-8 governance actions, UX-9 model-assisted objective preparation, UX-10 Release Center, UX-11 Operations Command Center, UX-12 Evidence & Provenance Inspector, UX-13/14 Agent & Skill Lifecycle centers, UX-15 Tool Registry & MCP Governance, UX-16 Tool Selection & Eligibility, UX-17 Policy Designer, UX-18 Policy Testing & Simulation, UX-19 Governance Audit Timeline, UX-20 Compliance & Assurance Dashboard, UX-21 Risk & Remediation, UX-22 Agent Observability, UX-23 Discovery Composition (all demo/live separated), UX-24 Agent Governance & Trust Center. Boundary invariants preserved throughout: no tool invocation, approval != authorization != execution, diagnostics are observations not proof.

The page contains responsive CSS breakpoints and a grouped left-rail navigation. It is not yet the full persistent shell described in `PRODUCT_UX_BLUEPRINT.md`.

## 4. Core feature readiness matrix

| Domain | Current readiness | Not yet delivered |
|---|---|---|
| Authentication boundary | Bearer dependency on protected API routes | Production identity provider, role model, tenant isolation, token lifecycle UX, rate limiting and audit trail |
| Intent / GoalSpec | Visual authoring and structural server validation + versioned template catalog (`/goalspec/templates`) + workspace revision provenance (`/workspaces/{id}/revisions`) | Semantic intent grounding, assisted GoalSpec synthesis beyond `objectives/prepare` |
| Registry | Read-only retained snapshot browsing + tool detail/intelligence views (UX-3) + deterministic facet counts + category filter (UX-15) | Live registry synchronization, trusted verification pipeline |
| Discovery | Core engine + persisted run records + reproducibility envelope + human-review gate | Side-by-side candidates, policy editor guided presets (implemented: read-only/egress-limited/strict-evidence), cancellation |
| Assurance | Certificate and counterexample surfaces + evidence inspector (UX-12) + audit ledger (full-ledger verify + cursor paging) + audit timeline (UX-19) + evidence freshness batch + agent sign/revoke parity + version/run diffs + recorded-activity endpoint (`/activity`) | Formal check documentation, exportable signed assurance package |
| Model metadata | Read-only catalog and artifact metadata + live runtime status/load/chat | Model serving at scale, measured benchmarks, controlled download and isolated inference |
| Runtime | Host diagnostics + read-only runtime observability workspace (UX-7) | Sandboxed MCP invocation, credential isolation, network controls, quotas, cancellation, event logs and output capture |
| Evaluation | Gold labels isolated from discovery endpoint | Dedicated evaluator service/API, benchmark scoring, experiment IDs and result provenance |
| Workspace lifecycle | Durable draft save/restore via `/api/v1/workspaces` (explicit save, optimistic concurrency) + immutable per-revision edit history (actor, digest, field-level paths) | Sharing and collaboration |
| Operations | Health/readiness, host probe, operations command center (UX-11), persisted audit ledger with full-ledger hash-chain verify + cursor paging (UX-19), per-version recorded-activity (`/activity`) | Structured logs, performance metrics and time series (require governed execution/telemetry — explicitly unavailable), deployment profiles, backup/recovery, production runbooks |

## 5. UX and engineering priorities

### P0 — Contract correctness and safety

- Preserve gold-label isolation between task browsing/discovery and evaluation.
- Make the distinction between selected toolkit, certificate validity, semantic alignment and runtime outcome explicit in every result state.
- Treat all registry metadata and annotations as untrusted declarations until independently verified.
- Add request/response contract tests for malformed policy/engine values and all discovery outcome shapes.
- Ensure sensitive bearer credentials are never echoed into responses, logs or rendered diagnostics.

### P1 — Application shell and workspace model

- Introduce a coherent shell with Overview, Workspace, Goal Design, Registry, Discovery, Assurance, Models and Diagnostics.
- Show actual capability status; planned features must be visibly unavailable, not clickable mock controls.
- Introduce a workspace draft model only when persistence semantics are defined. Until then, label browser state as ephemeral.
- Add a pre-discovery review summary of prompt, goals, selected tools, policy and model-profile calibration state.

### P2 — Authoring and registry workflow

- Add a dependency graph with a table alternative.
- Add searchable semantic type and effect references.
- Add a tool details panel including declared schema, annotations, source, trust classification and available provenance.
- Make the selection basket visibly independent of pagination and filters.
- Preserve deterministic “replace request toolset” semantics when importing registry selections.

### P3 — Discovery and assurance

- Present selected / abstained / invalid request / service error as distinct outcomes.
- Explain S/C/P/E/L/V mandatory checks separately from M/B diagnostics, including what each check cannot prove.
- Show goal-level witnesses and bindings with source and trust status.
- Make counterexamples actionable and retain them when no certificate is present.
- Provide a reproducibility summary (request digest, registry snapshot, profile ID, engine settings and timestamp) when the backend can supply it.

### P4 — Models and diagnostics

- Display model catalog data as unverified external metadata.
- Show every memory-estimate assumption and distinguish estimates from measured device capacity.
- Distinguish host GPU detection, model loadability and actual inference readiness.

### P5 — Evaluation and runtime (separate security projects)

- Implement evaluation behind a distinct service boundary with controlled access to benchmark gold labels.
- Do not implement tool execution as a UI-only feature. It requires sandboxing, credential isolation, network policy, budget enforcement, cancellation, audit events and output capture.
- Display runtime results independently from discovery certificates.

## 6. Required validation matrix

| Layer | Minimum verification |
|---|---|
| API | Authentication, schema validation, bounds, error mapping, no secret leakage, gold-label isolation |
| Discovery semantics | Selected, abstained, no-certificate, invalid-certificate, empty toolkit, and counterexample cases |
| Frontend behavior | Import benchmark task, clear stale goals, replace tools, pagination/filter selection persistence, manual JSON synchronization, loading/error/empty states |
| Assurance semantics | Mandatory vs diagnostic checks, missing evidence, no-certificate state, no execution claim |
| Accessibility | Keyboard-only flow, focus order, labels, live-region announcements, contrast and narrow viewport |
| Browser/Colab | Run the exact commit SHA; record browser, notebook/runtime, API health, screenshots or logs, and observed defects |
| CI | Full test suite and static checks on the exact pushed SHA |
| Merge | Only after CI and required runtime validation; merge requires explicit owner authorization |

## 7. Validation status at this audit baseline

- Integration branch `devin/studio-ux-integration-v1` tip `ac14b7ba25ec0a7fb46b6496ca93634c35474c5f`: 696 tests green locally; notebook acceptance verified on Colab at `b84d53e` (229 v2 + 122 v3/API + readiness/intelligence/governance cells).
- Earlier baseline `e641fc7412dbb77ae44304562820db619aaf7359`: GitHub Actions run completed successfully.
- Repository tests in `tests/test_studio_api.py`: 52 test functions are present at this baseline; this count is a static source inspection, not a claim that each was executed locally during this audit.
- The current PR's browser/Colab workflow has not been executed by this agent in this session. Browser behavior remains unverified.
- No upstream repository was fetched or cloned. Retained repository data remains the source of truth.
- No `git apply --check` workflow is part of this process.
- PR #9 remains unmerged.

## 8. Source map

- API and request contracts: `src/taas/studio/api.py`
- Frontend and interaction logic: `src/taas/studio/static/index.html`
- Model metadata adapter: `src/taas/studio/models.py`
- Hardware and memory diagnostics: `src/taas/studio/runtime.py`
- API/frontend regression tests: `tests/test_studio_api.py`
- Certificate validity semantics: `tests/test_certificate_validity.py`
- Discovery certificate gate: `tests/test_engine_certificate_gate.py`
- Product/UX target architecture: `docs/studio/PRODUCT_UX_BLUEPRINT.md`
- API usage: `docs/studio/API_QUICKSTART.md`
