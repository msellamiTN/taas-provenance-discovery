# TaaS Engineering Execution Tracker

> Living source of truth for engineering work. Update this file in the same change that advances a task. A task is **not Done** because code exists: implementation, build, automated tests, and the relevant runtime verification must be recorded independently.

**Product target:** TaaS Professional Studio — from objective to governed execution.  
**Repository:** `msellamiTN/taas-provenance-discovery`  
**Tracking baseline:** 2026-11-03  
**Tracker PR:** [#22 — Add evidence-based TaaS engineering execution tracker](https://github.com/msellamiTN/taas-provenance-discovery/pull/22) (open, draft; currently based on PR #21; its CI remains blocked by the three assertions repaired in PR #23).  
**Current integration baseline:** PR #20 head `4a3e4e460f2556f6556b1ef4736f991337cf32c2`; PR #21 head `8211e36b586a6ef75d185fb1b4c5dd5171037697` (both open, draft; PR #21 targets PR #20).  
**Status vocabulary:** `Planned`, `In progress`, `Implemented`, `Built`, `Tested`, `Run verified`, `Blocked`, `Done`. Use `Done` only when all required gates pass.

## 1. Definition of done

A task may be marked **Done** only when its record contains:

1. **Scope:** acceptance criteria and explicit non-goals.
2. **Implementation:** commit SHA and changed paths.
3. **Build:** exact command and successful result (or documented reason no build applies).
4. **Tests:** exact test command, pass/fail/skip counts, and CI run URL.
5. **Runtime:** actual launch/run/smoke evidence for the affected runtime path; distinguish local, CI, Colab and production.
6. **Safety and UX:** trust boundaries, failure states, accessibility/responsive behavior where applicable.
7. **Documentation:** operator/developer instructions updated.
8. **Residuals:** known limitations, follow-up issue/task IDs, owner and next action.

Never infer a live runtime result from static tests, a successful build, hardware detection, metadata inspection, or a green pre-execution certificate.

## 2. Current verified baseline

| Item | Evidence | State |
|---|---|---|
| PR #20 — Model Engineering Workbench | Open draft; head `4a3e4e460f2556f6556b1ef4736f991337cf32c2` | Model workbench + global header authentication + Colab operator guide implemented; CI/Colab validation still needs evidence |
| PR #21 — Colab launcher alignment | Open draft; head `8211e36b586a6ef75d185fb1b4c5dd5171037697`; 13 commits / 6 files | Notebook now pins PR #20 head, binds Uvicorn to `0.0.0.0:8000`, probes readiness via loopback, and tests/documentation cover proxy `NOT_FOUND`; validation incomplete |
| PR #21 GitHub Actions run #184 | [Run 41659536638](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/41659536638) | Historical failure on earlier head; later notebook/proxy commits have not yet been confirmed green by a retrieved run |
| CI failure detail | Job `unit-tests`, step 5 failed; available job summary does not expose failing assertion/log | Root cause **not yet established** |
| Colab T4 live model load/inference | No execution evidence in PR #21; latest notebook pin `4a3e4e460f2556f6556b1ef4736f991337cf32c2` | Not run / unverified |
| Persistent workspace and multi-user isolation | Not present in audited Studio implementation | Not implemented |
| MCP tool invocation | Execution gateway authorization primitives exist, but no MCP `tools/call` invocation path | Not implemented |

The PR #21 failure must be diagnosed from the job log before changing code. Do not guess the cause or mark the regression suite passed.

## 3. Active work queue

### P0 — Stabilize the current integration chain

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| CORE-001 | Diagnose PR #21 CI failure | Capture failing test name, traceback and reproducible command; classify regression vs environment; link evidence | **Done — 3 stale UI assertions identified** |
| CORE-002 | Repair PR #21 regression | Minimal fix with regression test; no unrelated refactor; commit linked to PR #21 | **Validated in PR #23; integration into PR #21 pending review/merge** |
| CORE-003 | Run full repository test suite | `python -m pip install -e ".[test,studio]"` then `python -m pytest -q`; record counts and environment | **Passed in GitHub Actions: 180 passed, 3 warnings (Python 3.11.17)** |
| CORE-004 | Build benchmark hypergraph | Run `python scripts/build_benchmark_hypergraph.py --outdir /tmp/taas-benchmark-hypergraph`; verify expected outputs | **Passed in GitHub Actions: 31 vertices, 569 hyperedges, 76 servers; artifact uploaded** |
| CORE-005 | Validate Colab notebook statically | Notebook JSON parse and notebook regression tests pass | Updated in PR #21; latest CI result not yet retrieved |
| CORE-006 | Validate Colab runtime | Launch exact pinned notebook; record `/health`, `/ready`, proxy opening, authentication, GPU/model revision, load, inference, latency/memory and errors; no synthetic success | Not run; user to rerun after proxy-binding fix |
| CORE-007 | Reconcile PR #20 → #21 stack | Confirm branch ancestry, no accidental divergence, all checks green before merge recommendation | In progress; PR #21 now pins exact PR #20 head |

### P1 — TaaS Professional Studio foundation

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| UX-001 | Canonical navigation shell | Fixed-width collapsible Midnight sidebar; active route; responsive workspace; canonical IA below | Planned |
| UX-002 | Design system | Cloud workspace, teal primary actions, slate secondary content, semantic status colors, typography, spacing, dark/light contrast | Planned |
| UX-003 | Capability-aware navigation | Implemented routes open real workspaces; future modules clearly marked unavailable, with no fake controls | Planned |
| UX-004 | Overview workspace | Workspace health, recent activity only from real data; explicit empty, loading, stale and error states | Planned |
| UX-005 | Navigation and responsive tests | Route coverage, keyboard navigation, narrow viewport behavior, active state and no dead links | Planned |

**Canonical information architecture**

- Overview
- BUILD: Model Studio; Agent Studio; Tools & MCP; Workflow Studio
- DISCOVER & ASSURE: Tool Discovery; GoalSpec Designer; Assurance Center
- OPERATE: Execution Gateway; Runs & Traces; Provenance; Evaluation
- ADMINISTRATION: Settings; Governance & Policies; Runtime & Resources

### P2 — Objective-to-governed-execution workspace

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| FLOW-001 | Shared task context | Stable objective/task context across workspaces; no silent loss when navigating | Planned |
| FLOW-002 | Lifecycle state model | Intent → agent/model selection → GoalSpec review → discovery → assurance → authorization → execution → trace | Planned |
| FLOW-003 | Explicit state semantics | Proposal, validated contract, discovery result, pre-execution assurance, approval, runtime outcome remain distinct | Planned |
| FLOW-004 | Human review gates | No generated GoalSpec or plan automatically invokes a tool | Planned |

### P3 — Model Studio integration

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| MODEL-001 | Model catalog and details | Search, inspect architecture/license/revision/files; metadata marked external/unverified | Implemented in PR #20 branch; integration verification pending |
| MODEL-002 | Runtime manager | Explicit load/unload, backend/device/precision and process status; errors visible | Implemented in PR #20 branch; runtime test pending |
| MODEL-003 | Inference playground and metrics | Real inference; measured latency/token/memory metrics clearly separated from estimates | Implemented in PR #20 branch; live validation pending |
| MODEL-004 | Immutable ModelRef | Pin provider, repository, revision, backend and runtime identity | Planned |
| MODEL-005 | Measured Model Capability Profile | Calibration dataset, measurements, confidence, limitations, timestamp and immutable model identity; never infer capabilities from name/metadata | Planned |
| MODEL-006 | Bind runtime identity to discovery | Discovery rejects profile/runtime identity mismatch; strict uncalibrated fallback remains fail-closed | Known integration gap |

### P4 — Agent Studio and GoalSpec lifecycle

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| AGENT-001 | Agent Designer | Objective, model, system instructions, context and configuration | Partially implemented in PR #19/#20 chain; verify |
| AGENT-002 | GoalSpec proposal and review | Generated proposal is editable, visibly untrusted until reviewed, and structurally validated | Implemented in PR #9/#19/#20 chain; tests to verify |
| AGENT-003 | Validation readiness | Structural checks, capability profile assessment and discovery readiness shown separately | Planned |
| AGENT-004 | No auto-execution | Tests prove model-generated plan cannot directly invoke MCP tools | Planned |

### P5 — Tools & MCP registry and provenance

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| MCP-001 | MCP server configuration and schema inspection | Existing read-only inspection behavior retained; no implication of invocation | Implemented; end-to-end test pending |
| MCP-002 | Versioned tool snapshots | Canonical definition hash, schema version, server identity and snapshot timestamp | Planned |
| MCP-003 | Evidence lifecycle | Source, verifier, trust level, freshness, expiry/revocation and evidence hash | Planned |
| MCP-004 | Registry-to-discovery binding | Discovery consumes an immutable registry snapshot, not arbitrary untracked definitions | Planned |
| MCP-005 | Provenance UI | Declared metadata vs independently verified evidence visually distinct | Planned |

### P6 — Discovery & Assurance Studio

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| DISC-001 | Real discovery engine integration | Existing `DiscoveryEngine.discover()` call preserved and tested | Implemented in current Studio branch; CI verification pending |
| DISC-002 | Capability hypergraph visualization | N-ary hyperedges, capability paths, tool nodes, typed inputs/outputs and readable large-graph behavior | Planned |
| DISC-003 | Joint-effects analysis | Show set-level interactions; never substitute pairwise compatibility for n-ary checks | Planned |
| DISC-004 | Assurance evidence explorer | Mandatory vs diagnostic checks, witnesses, counterexamples, provenance hashes and freshness | Partially implemented; UX enhancement planned |
| DISC-005 | Certificate semantics | UI states certification is pre-execution evidence, not semantic task success or runtime success | Existing documentation; browser verification pending |
| DISC-006 | Reproducibility envelope | GoalSpec digest, model profile ID, registry snapshot, policy, engine config and timestamp | Planned |

### P7 — Workflow Studio

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| WF-001 | Visual workflow authoring | Typed nodes/edges, validation before run, readable graph and accessible table alternative | Planned |
| WF-002 | Governed composition | Composed workflow references certified toolsets and explicit approval boundaries | Planned |
| WF-003 | Versioned workflow artifacts | Immutable versions, diffs, provenance and rollback | Planned |

### P8 — Execution Gateway (separate security milestone)

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| EXEC-001 | Preserve authorization primitives | Approval bound to actor/server/tool/arguments/GoalSpec/policy/tool hash/assurance evidence | Implemented primitives; tests and review required |
| EXEC-002 | Isolated MCP workers | Per-run process/container isolation, filesystem/network policy and resource limits | Not implemented |
| EXEC-003 | Credential isolation | Secret broker, least privilege, no secret exposure in prompts/logs/traces | Not implemented |
| EXEC-004 | Invocation and cancellation | Real MCP `tools/call`, timeout, cancellation, retry/idempotency semantics | Not implemented |
| EXEC-005 | Policy and budget enforcement | Deny by default, approval gates, quotas, rate limits, spend/time budgets | Not implemented |
| EXEC-006 | Audit events and redaction | Append-only events, redacted arguments/results, actor attribution | Not implemented |

**Hard gate:** do not expose an “Execute” action until EXEC-002 through EXEC-006 have security design, implementation and adversarial tests. Authorization approval is not successful execution.

### P9 — Runs, Traces, Provenance and Evaluation

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| OPS-001 | Durable run records | Persistent run state, immutable config snapshot and artifact references | Not implemented |
| OPS-002 | Traces | Actual tool calls, timing, outputs/errors, policy decisions and correlation IDs | Not implemented |
| OPS-003 | Provenance graph | Evidence lineage from source/tool/model/spec through discovery and execution | Planned |
| OPS-004 | Evaluation service | Separate evaluator boundary; benchmark gold labels never exposed to agent/discovery path | Research scripts exist; integrated service not implemented |
| OPS-005 | Reproducible comparisons | Versioned datasets, model/profile, registry, policy, seeds and metrics | Planned |

### P10 — Governance, operations and production readiness

| ID | Task | Acceptance / evidence required | Status |
|---|---|---|---|
| GOV-001 | Workspace/project persistence | Durable workspace, versioning, restore and audit | Not implemented |
| GOV-002 | Multi-user/tenant isolation | Identity, RBAC, tenant boundaries and cross-tenant negative tests | Not implemented |
| GOV-003 | Policy administration | Versioned policy-as-code, validation, conflict detection and approval lifecycle | Planned |
| GOV-004 | Runtime/resource manager | Real resource state, quotas, health and operator actions | Partially implemented diagnostics only |
| GOV-005 | Observability | Structured logs, metrics, traces, alerts and retention policy | Not implemented |
| GOV-006 | Deployment and recovery | Supported deployment profiles, secrets, backups, restore and runbooks | Not implemented |

## 4. Product workflow and trust invariants

The platform must enforce these distinctions in API contracts, UI labels, logs and tests:

- Model metadata is not measured capability.
- Model load success is not proof of capability calibration.
- MCP schema inspection is not provenance verification.
- Certified toolkit is not an executed toolkit.
- Valid authorization is not successful execution.
- Structural GoalSpec validity is not semantic correctness.
- Discovery certification is pre-execution evidence, not runtime success.
- A model-generated plan is a proposal, not executable authority.
- Unknown/unverified state must not be styled as success.

## 5. Engineering execution protocol

For each task:

1. Inspect the actual base branch, open PRs, relevant code and tests.
2. Write acceptance criteria before implementation.
3. Create a focused branch from the correct stack head.
4. Implement the smallest coherent change; update docs and regression tests.
5. Run formatting/lint/build checks that the project actually configures.
6. Run focused tests, then the full relevant test suite.
7. Launch the affected service/runtime and perform a smoke test.
8. Inspect GitHub Actions; record exact run URL and job outcomes.
9. Update this tracker with commit SHA, commands, results, limitations and next task.
10. Open/update a draft PR; do not merge automatically.

### Evidence log

| Date | Task | Commit / PR | Build | Tests | Runtime | Outcome / next action |
|---|---|---|---|---|---|---|
| 2026-11-03 | PR21 CI baseline | PR #21 / `a9d629e7e710e6622c0b10eed06ece29ca62ab14` | Dependency installation passed in CI | **177 passed, 3 failed**: stale title assertion; brittle nested-panel comment assertion; exact CSS-string assertion | Colab T4 not run | Root cause established from job logs; see PR #23 fix |
| 2026-11-03 | Studio regression test repair | [PR #23](https://github.com/msellamiTN/taas-provenance-discovery/pull/23) / `1ce2a01ca62ab07c8890ba7ad7ceed13b9a20c5c` | [GitHub Actions run #41663531105](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/41663531105) — **success** | **180 passed, 3 warnings**; hypergraph build succeeded; artifact uploaded | Test-only patch; no runtime product code changed | PR #23 is green; integrate it into PR #21 before treating PR #21 as green |
| 2026-11-03 | Benchmark hypergraph build | PR #23 CI run #41663531105 | **Passed** | Build report: 31 vertices, 569 hyperedges, 76 servers, 736 required argument occurrences, 821 optional arguments | GitHub-hosted CI execution; not a production runtime deployment | Inspect benchmark artifact and preserve reproducibility metadata

## 6. Mandatory Colab validation gate

Every PR must be executed in Google Colab against its exact head SHA. GitHub Actions and static notebook checks are necessary but not sufficient. The level-based procedure, current PR matrix, evidence template and PASS/FAIL/BLOCKED semantics are defined in [COLAB_PR_VALIDATION_PROTOCOL.md](COLAB_PR_VALIDATION_PROTOCOL.md).

**Current decision:** PRs #20–#23 have no recorded Colab execution evidence and therefore remain **NOT RUN** for Colab. PR #20 requires Studio/API smoke and actual model load/inference on a T4 (or a documented hardware block); PR #21 requires opening the notebook from its own branch and running it top-to-bottom; PR #22 and #23 require the applicable clean-runtime and regression checks, with product/hardware levels marked N/A only for the documented reasons.

## 7. Immediate next actions

1. Run the updated PR #21 regression workflow and inspect the exact head SHA and job logs; do not treat an empty workflow lookup as a pass.
2. Have the operator restart Colab and execute the updated notebook top-to-bottom; capture readiness and proxy results.
3. Verify global Studio authentication using the current runtime token, then validate GoalSpec and discovery workflows.
4. Perform actual model load/inference on a T4 only when one is allocated; record model/revision/device/precision/latency/memory.
5. Review PR #20/#21 stack ancestry and CI before any merge recommendation.
6. Once this integration is validated, implement the TaaS Professional shell (P1) on a branch based on the latest validated stack head.

## 8. Change log

- **2026-11-03:** Initial tracker created from the audited repository and PR #20/#21 state; submitted as draft PR #22. No unverified feature is marked Done.
- **2026-11-03:** Diagnosed PR #21 CI failures from full job logs; test-only repair in draft PR #23 passed CI (180 tests) and benchmark hypergraph build. PR #21 itself still needs the repair integrated.

- **2026-11-03:** Added mandatory exact-SHA Colab validation protocol for every PR. Current PRs #20–#23 are explicitly marked NOT RUN in Colab; CI success is not treated as Colab evidence.


- **2026-11-03:** Fixed the Colab proxy launch configuration in PR #21: Uvicorn now binds to `0.0.0.0:8000`, while `/health` and `/ready` probes use `127.0.0.1:8000`. Added a regression assertion and `RpcError(NOT_FOUND)` operator troubleshooting. PR #21 notebook is pinned to exact PR #20 head `4a3e4e460f2556f6556b1ef4736f991337cf32c2`; PR #21 head is `8211e36b586a6ef75d185fb1b4c5dd5171037697`. Live Colab rerun and latest CI confirmation remain pending.


- **2026-11-03:** PR #22 initially failed its CI run because its original base (`feature/colab-model-agent-studio`) still contained the three stale assertions. A temporary retarget to PR #23's branch was reverted because PR #22's head does not contain that branch's commit ancestry; GitHub reported the PR as non-mergeable. PR #22 remains based on PR #21 and must be revalidated after PR #23's regression repair is integrated into PR #21. No fresh passing PR #22 run has been observed.
