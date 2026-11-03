# TaaS Studio — Product and UX Blueprint

Status: design baseline for the next Studio UX iteration. This document describes the target experience; it does not claim that every capability is implemented.

## 1. Product model

TaaS Studio is a provenance-aware tool-discovery control plane. Its primary job is to help an operator move from a user request to an explainable, policy-constrained toolkit recommendation.

Studio must keep four outcomes visibly separate:

1. **Intent authored** — a human or future analyst provider has expressed the task as a GoalSpec.
2. **Discovery computed** — the engine has searched the retained capability registry and proposed a toolkit or abstained.
3. **Pre-execution assurance** — structural validation and certificate checks establish only the properties they are designed to establish.
4. **Runtime outcome** — a separately implemented and isolated runtime has actually invoked tools and recorded results.

A selected toolkit is not task completion. A valid certificate is not runtime evidence. Metadata, schemas and annotations are declarations unless supported by independently verified provenance.

## 2. Target information architecture

Use a persistent left navigation rail on desktop and a compact drawer on smaller screens:

- **Overview** — service readiness, active workspace, recent local sessions, capability availability.
- **Workspaces** — create/open a discovery workspace; benchmark and custom tasks.
- **Goal design** — visual GoalSpec authoring, dependency graph, semantic type/effect catalog, structural validation.
- **Tool registry** — retained datasets, task browser, registry search, tool detail and selection basket.
- **Discovery** — policy, model profile, engine settings, run discovery, candidate comparison and abstention.
- **Assurance** — certificate checks, provenance evidence, goal witnesses, policy violations, counterexamples.
- **Models** — model catalog, artifact metadata, compatibility and memory estimates.
- **Runtime** — host diagnostics and, only when implemented, isolated runtime sessions and execution traces.
- **Experiments** — benchmark evaluation, gold-label evaluation boundary, metrics and reproducibility.
- **Settings** — API connection, tokens, data source/version, calibration profile and preferences.

Do not show a navigation destination as operational when it is only a planned capability. Mark it as unavailable/roadmap or hide it behind an explicit experimental-capabilities area.

## 3. Primary end-to-end journey

### Step A — Create workspace

- Name the workspace and choose a source: retained benchmark task or custom prompt.
- Show dataset snapshot/version and provenance at the point of selection.
- Explain that gold labels are withheld from discovery.
- Persist the request locally only if session persistence is explicitly implemented; otherwise label it as an in-memory draft.

### Step B — Define intent

- Keep the natural-language objective visible above the GoalSpec.
- Provide a guided goal-card editor with progressive disclosure: outcome, operation class, semantic output, inputs, effects, delegation, dependencies, cardinality, exactness, language and optionality.
- Offer a dependency graph view and a compact table view for multi-goal tasks.
- Provide examples as insertable templates, clearly marked as examples and never silently retained when a benchmark task is imported.
- Show local structural diagnostics beside the field and a server-validation summary.
- State clearly: structural validity does not prove semantic fidelity to the prompt.
- Advanced JSON is an expert escape hatch; edits must be synchronized explicitly and visibly.

### Step C — Select capabilities

- Search by server, tool name, description, category, source and semantic capability.
- Display tool details in a side panel: declared inputs/outputs, effects, annotations, source, evidence/trust state and definition hash when available.
- Keep a selection basket independent of pagination and filters.
- Provide explicit actions: add selected, replace request toolset, clear selection. Never silently merge stale sample tools into a benchmark selection.
- Label all unverified metadata as declared/unverified.

### Step D — Configure discovery

- Separate policy configuration from engine tuning.
- Provide safe presets with a readable diff of required/allowed/forbidden effects and trust thresholds.
- Explain model-profile identity, calibration state and threshold. An uncalibrated profile must be conspicuous.
- Validate the complete request before enabling discovery.
- Present a review screen summarizing prompt, goals, tools, policy and profile.

### Step E — Inspect the decision

The result screen must have a clear decision header:

- Toolkit selected / abstained / request invalid / service error.
- Number of goals, selected tools, candidate tools, search regime and elapsed time.
- Goal coverage table: goal, delegation class, witness, selected binding, provenance status.
- Certificate: mandatory checks S/C/P/E/L/V and diagnostic checks M/B, with expandable definitions and witness data.
- Counterexample: kind, affected goal/check, reason, evidence and suggested remediation.
- Explicit status banner: **No MCP tool was executed by discovery**.
- Never label a selected toolkit as “success” without an independently defined evaluation result.

### Step F — Evaluate and execute (future, separate subsystems)

- Evaluation may access benchmark gold labels only through a separate evaluator boundary; discovery APIs and analyst inputs must not receive gold labels.
- Runtime execution requires a separately implemented sandbox, credentials isolation, network policy, budgets, cancellation, audit events and output capture.
- Runtime results must be displayed separately from pre-execution certificates.

## 4. Feature inventory and product status

| Capability | Current surface/API | UX treatment |
|---|---|---|
| Health/readiness | `/health`, `/ready` | Service status, token readiness, calibration state |
| Retained benchmark datasets | `/api/v1/bench/datasets` | Dataset catalog with snapshot/source |
| Benchmark task browsing | `/api/v1/bench/tasks` | Search, category, pagination; never expose gold labels |
| Retained tool registry | `/api/v1/bench/tools` | Search, filter, inspect, selection basket |
| GoalSpec structural validation | `/api/v1/goals/validate` | Inline field errors and dependency graph |
| Discovery | `/api/v1/discover` | Review request, run, explain selection/abstention |
| Certificate | Discovery response | Assurance panel with mandatory vs diagnostic checks |
| Counterexamples | Discovery response | Actionable failure explanation |
| Model search/details/artifacts | `/api/v1/models/search`, `detail`, `artifacts` | Model catalog and metadata inspection; no execution claim |
| Memory estimate | `/api/v1/models/estimate-memory` | Assumption-aware estimate with uncertainty |
| Hardware diagnostics | `/api/v1/runtime/hardware` | Host/GPU diagnostics only; not inference readiness |
| Analyst LLM provider | Core has role/backend abstractions; no Studio provider flow | Mark unavailable until integrated, tested and configured |
| Runtime tool invocation | Not exposed by current Studio API | Roadmap; never simulate execution |
| Durable workspaces/history | Not implemented in current API | Roadmap; do not imply persistence |
| Benchmark evaluator | Separate boundary required | Keep gold labels isolated from discovery |
| Experiment dashboard | Existing experiment scripts/results, no integrated Studio workflow | Roadmap with reproducible run IDs and artifact provenance |

## 5. Visual and interaction system

- Calm technical workspace, high information density without dashboard clutter.
- One primary action per step; secondary actions are visually quieter.
- Use consistent status vocabulary: Draft, Needs attention, Structurally valid, Discovery selected, Abstained, Certificate valid/invalid, Not verified, Not executed, Runtime completed/failed.
- Do not use green certificate styling to imply task completion. Pair every status with a precise textual explanation.
- Use side panels for details and evidence; avoid dumping raw JSON as the default experience.
- Keep raw request/response JSON available under an advanced inspector with copy/export controls.
- Tables need stable sorting, empty states, loading states, pagination and clear filter reset.
- Long-running operations need cancellation only where the backend supports it; otherwise do not show a fake cancel control.
- Errors must identify the failed request, HTTP status where safe, and a recovery action without exposing secrets.

## 6. Accessibility and responsive behavior

- Semantic landmarks and heading hierarchy; keyboard-operable navigation and controls.
- Visible focus rings, labels, help text and field-level error association.
- Status updates announced through polite live regions; urgent failures announced assertively.
- Do not communicate state by color alone.
- Support reduced motion and zoom/reflow at narrow widths.
- On mobile, convert dense tables to stacked summaries with a detail expansion; keep critical status and primary action visible.
- Dependency graph must have an equivalent textual/table representation.

## 7. Security and trust UX

- Never display or log bearer tokens after entry; provide explicit reveal/copy only if securely supported.
- Show the configured API origin and connection state.
- Keep benchmark gold labels outside discovery responses, browser state and analyst payloads.
- Treat tool metadata and annotations as untrusted declarations.
- Distinguish evidence source, verifier, trust level and freshness; missing evidence is not positive evidence.
- Show policy decisions in human-readable language and link them to the relevant tool/effect.
- No runtime execution without explicit user intent, isolated execution controls and an auditable confirmation step.

## 8. Acceptance criteria for the UX redesign

1. A first-time user can complete a guided benchmark-to-discovery workflow without editing raw JSON.
2. Importing a benchmark task removes all example goals and forces the author to author or explicitly import a reviewed GoalSpec.
3. Importing selected registry tools replaces the active request toolset; no stale demo tool can remain implicitly.
4. Selection persists across registry pagination and filtering, with a visible count and inspectable basket.
5. Every goal has a visible authored description and field-level validation.
6. A dependency graph and table provide equivalent information.
7. The review step makes prompt, goals, tools, policy and model calibration visible before discovery.
8. Result state distinguishes selected toolkit, goal witnesses, certificate validity, semantic alignment and runtime execution.
9. Every certificate check explains what it proves and what it does not prove.
10. No benchmark gold label is exposed to discovery or analyst-facing flows.
11. All API-backed controls have loading, empty, error and success states.
12. Keyboard-only navigation and narrow-screen layout are tested.
13. Automated tests cover state transitions and request payload integrity, not only static copy.
14. Browser validation is recorded against the exact commit SHA and runtime environment.

## 9. Implementation sequence

- **UX-0 — Audit and contract freeze:** enumerate all endpoints, payloads, response states and trust boundaries; add contract tests.
- **UX-1 — Application shell:** navigation, workspace header, API connection and capability-aware feature states.
- **UX-2 — Goal design:** improve visual editor, graph/table views, inline diagnostics and examples.
- **UX-3 — Registry experience:** robust filters, detail panel, persistent selection basket and deterministic import/replace semantics.
- **UX-4 — Discovery review and results:** request review, explicit statuses, certificate definitions, provenance drill-down and counterexample remediation.
- **UX-5 — Models and diagnostics:** structured catalog cards, assumptions for estimates and clear hardware-readiness boundaries.
- **UX-6 — Evaluation and experiments:** isolated gold-label evaluator and reproducible experiment history.
- **UX-7 — Runtime:** only after sandbox, policy enforcement, credential isolation, observability and cancellation are implemented.
- **UX-8 — Hardening:** accessibility, responsive browser tests, security review, performance and operational readiness.

Each increment must have API/contract tests, frontend behavior tests, documentation, CI against its exact commit and Colab/browser validation before merge. A missing browser-control capability must be recorded as an unverified validation item, never as a pass.
