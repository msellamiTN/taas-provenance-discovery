# Phase 0 — TaaS PR audit (#44–#46)

**Audit date:** 2026-11-04  
**Repository:** `msellamiTN/taas-provenance-discovery`  
**Scope:** PR metadata and ancestry, changed code, regression tests, Colab notebook pins, CI logs, dependency declarations.  
**Disposition:** Corrections committed to PR #46. No PR merged.

## Executive result

The three pull requests form a valid, strictly stacked sequence:

| PR | Base | Audited head | CI run | Regression result |
|---|---|---|---|---:|
| [#44 Hypergraph discovery actions](https://github.com/msellamiTN/taas-provenance-discovery/pull/44) | `feature/hypergraph-explorer-hardening` | `2c08b48f8f0cab0b31de7d22da4345136646926b` | [41740068540](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/41740068540) | 233 passed, 1 warning |
| [#45 Discovery refresh persistence](https://github.com/msellamiTN/taas-provenance-discovery/pull/45) | #44 head | `efdbb7d025789127323fba5086a6385245582ccc` | [41742920244](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/41742920244) | 234 passed, 1 warning |
| [#46 Studio navigation/workflow hardening](https://github.com/msellamiTN/taas-provenance-discovery/pull/46) | #45 head | `324ded546cfc13f19dc512b823fa1263dc2ffb6d` | [41796615806](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/41796615806) | 242 passed, 1 warning |

All three PRs remain **open, draft, and unmerged**. Each PR's base SHA equals the preceding stack head. Commit comparisons confirm that each notebook implementation pin is an ancestor of its corresponding PR head.

## PR #44 — Hypergraph Explorer discovery actions

**Notebook implementation pin:** `f7fbe1ddf27e94ebabe267d5d417dab9da793f22`  
**CI:** success; 233 tests passed.

Reviewed behavior:
- Explorer Run action delegates to the existing Discovery button/handler; it does not create a second request path.
- Discovery uses the existing authenticated `POST /api/v1/discover` endpoint.
- Hypergraph data is rendered only from the Core-generated API projection.
- GoalSpec navigation and shared status are wired into the existing Studio.
- Integration fixture is contract metadata; it does not contact an MCP server or invoke a tool.
- The notebook keeps the existing Colab runtime, checkout, Studio process, token and proxy workflow; no Playwright dependency was introduced.

Assessment: no confirmed defect found in the PR-specific implementation during this audit. CI and notebook structure checks pass. Live Colab/browser acceptance remains an operator gate, not a CI claim.

## PR #45 — Discovery result refresh persistence

**Notebook implementation pin:** `888fefa5f14ad31ef367a7bdf560fcd1c6f0338e`  
**CI:** success; 234 tests passed.

Reviewed behavior:
- Successful API responses are saved as a versioned, bounded `sessionStorage` snapshot.
- The snapshot is tab-scoped UI state, not durable server-side run history.
- The bearer token is not stored in the snapshot.
- Refresh restores the displayed result without rerunning Discovery.
- A failed subsequent request retains the last successful projection and labels it as potentially stale.
- The projection renderer remains gated by the API's projection status; no graph is synthesized in the browser.

Assessment: behavior is consistent with the documented scope. The persistence mechanism is intentionally browser-local and must not be described as durable audit history. Browser storage remains accessible to same-origin JavaScript and is not an encrypted evidence store.

## PR #46 — Navigation and workflow hardening

**Original failing head:** `920a41ddd8191e784a606916e5b7a46b094de1cb`  
**Corrected head:** `324ded546cfc13f19dc512b823fa1263dc2ffb6d`  
**Notebook implementation pin:** `c24c0f1eee362a2f9ef516474fa567dcc6dd0aab`  
**Final CI:** [41796615806](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/41796615806), success; 242 passed, 1 warning.

### Confirmed failure and correction

The original PR #46 workflow failed with **6 failures and 236 passes**. The failures were stale assertions in four existing test modules. They expected the former navigation contract:
- Skip link targeting `#overview` instead of the new complete `#overview-workspace`.
- Direct `.hidden` assignment to siblings instead of the router-owned `hideForNavigation` mechanism.
- The previous overview navigation href.
- The previous compact inline pipeline selector rather than the refactored destination lookup.

The implementation change was intentional: navigation now records only the visibility changes it owns, restores those changes before routing, preserves the global runtime overview, and keeps Discovery's coupled GoalSpec/Run/result context together. Reverting the implementation to satisfy obsolete string assertions would have undone the intended workflow behavior.

Updated the four affected test modules:
- `tests/test_studio_api.py`
- `tests/test_studio_navigation_shell.py`
- `tests/test_studio_workspace_isolation.py`
- `tests/test_taas_model_workbench.py`

The tests now assert the current behavior and state-ownership contract. The complete CI workflow then passed, including the regression suite, benchmark hypergraph build and artifact upload.

### Navigation and workflow review

Verified in source/tests:
- Navigation and pipeline destinations exist and IDs are unique.
- Navigation handles `popstate` and `hashchange`; route changes use browser history.
- Runtime overview remains globally visible.
- Overview includes both hero and lifecycle pipeline.
- Benchmark prompt handoff routes to GoalSpec.
- Discovery nested destinations retain the Run action and result context.
- Responsive navigation has tablet and mobile grid breakpoints.
- Skip link targets the full Overview workspace.
- No browser-side semantic reachability or hypergraph generation was introduced.

The new navigation tests are static/structural checks. They do not prove actual visual layout, focus behavior or browser history behavior in a real browser. Those remain manual browser acceptance items.

## Notebook and runtime checks

For each PR, the notebook was fetched from that PR's branch and parsed as valid nbformat 4 JSON. The notebook's `TAAS_COMMIT` matches the corresponding `INTEGRATED_STUDIO_COMMIT` test constant. GitHub commit comparisons confirm each pin is in the PR's ancestry.

The notebook code installs `.[studio,hf]`, verifies imports, creates an ephemeral token, starts one Uvicorn process, checks health/readiness and reuses the Colab proxy variable on reruns. CI compiles all Python code cells through `test_colab_code_cells_are_valid_python`.

**Not performed in this audit:** executing the notebook in a live Colab T4 runtime, opening the proxy in Chrome, visual QA, or manually testing browser Back/Forward and refresh interactions. No such validation is claimed.

## Dependencies and reproducibility

No dependency manifest was changed by PRs #44–#46. The current `pyproject.toml` uses lower-bound ranges (for example `fastapi>=0.110`, `uvicorn[standard]>=0.27`, `httpx>=0.27`, `pydantic>=2.6`, and `torch>=2.2` in the optional HF extra). CI installs `.[test,studio]`; Colab installs `.[studio,hf]`.

Findings:
- CI successfully resolved and installed the dependency set for all three passing runs.
- The suite reports one Starlette/httpx TestClient deprecation warning. It is non-blocking, but should be tracked before dependency upgrades make it an error.
- There is no lockfile or constraints file in this change set. Reproducibility across future CI/Colab runs is therefore weaker than an exact pinned environment.
- The HF extra is intentionally large and version-floating; Colab installation time and compatibility can vary with the preinstalled runtime.

No speculative dependency pins were added during this audit. A dedicated dependency-management change should establish the supported Python matrix, lock/constraints strategy, and tested Colab package set rather than introducing arbitrary pins into these UI PRs.

## Safety and scope invariants

This audit did not enable MCP invocation, governed execution, isolated workers, authorization grants, or durable run history. Model/Agent workspaces remain limited to inspection, explicitly loaded local inference and GoalSpec drafting. Discovery and Assurance remain inspection/evidence workflows. A selected toolkit, valid discovery certificate, or integrity-verified evidence record is not authorization to execute.

## Phase 0 disposition

- [x] Verify PR state, stack bases and commit ancestry.
- [x] Inspect PR-specific code paths and regression coverage.
- [x] Verify notebook pins and nbformat structure.
- [x] Inspect dependency declarations and CI resolution.
- [x] Diagnose and correct the six confirmed PR #46 regression-test failures.
- [x] Confirm final PR #46 CI is green (242 passed).
- [ ] Run the maintained notebook in Colab against the pinned revision.
- [ ] Perform manual browser/visual acceptance, including navigation history, nested workspace transitions, refresh restoration and responsive layouts.
- [ ] Obtain explicit review/approval before any merge.

**Conclusion:** Phase 0 code/CI remediation is complete. Phase 0 operator acceptance is still pending. All three PRs remain unmerged.
