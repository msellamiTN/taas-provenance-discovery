# Gate 0 Baseline Inspection — TaaS

**Status: PARTIALLY COMPLETED — LOCAL EXECUTION BLOCKED**

## Scope and baseline identity

- Repository: `msellamiTN/taas-provenance-discovery`
- Inspected ref: `main`
- Baseline commit: `7d44fa66e0bc4250f8d9a11ccb7e06a5cdc43dd5`
- Remote tree entries: 183
- Capture date: 2026-11-01
- Inspection method: GitHub Git Trees API and read-only retrieval of source files.
- This is a remote repository inspection, not a verification of the user's local checkout.

The full path inventory and Git object IDs are in [inventory.json](../baselines/7d44fa66e0bc4250f8d9a11ccb7e06a5cdc43dd5/inventory.json).

## Execution environment available in this session

| Item | Observation |
|---|---|
| OS | Linux x86_64 (container runtime) |
| Python | 3.13.5 |
| Git | 2.47.3 |
| Codex CLI | Not installed / not on PATH |
| Local repository clone | Not present |
| GitHub network from container | DNS resolution failed for github.com |
| GitHub read access | Available through connected GitHub integration |

A clone attempt failed with `Could not resolve host: github.com`. Therefore no local Codex session, local Git status, dependency install, pytest run, experiment execution, or local SHA-256 inventory could be performed. No claim is made that any experiment was executed in this container.

## Repository inventory

| Area | Tracked paths |
|---|---:|
| `data/` | 99 |
| `results/` | 20 |
| `experiments/` | 12 |
| `src/` | 28 |
| `docs/` | 8 |
| `tests/` | 1 |
| Total tree entries | 183 |

Data subtree counts: `raw/` 7, `processed/` 4, `llm_records/` 9, `llm_inputs/` 7.

Historical results include 11 JSON result/calibration files, six PNG figures, `results/run_all.log`, and `results/run_log.json`. The inventory records each Git blob object ID and file size. Git blob IDs are used only as immutable tree identifiers; they are **not** represented as SHA-256 content hashes.

## Entry-point and write-side-effect audit

### `reproduce.sh`

Observed sequence:
1. `pip install -r requirements.txt` — modifies the Python environment.
2. `python -m pytest -q` — test execution.
3. `PYTHONPATH=src python -m taas.data.registries` — rebuilds `data/processed/registry_merged.json`.
4. `python experiments/run_all.py 2>&1 | tee results/run_all.log` — runs the full experiment pipeline and overwrites the log.

**Do not run this script against the historical checkout.** It modifies a tracked processed dataset and historical results/logs.

### `experiments/run_all.py`

Runs E0, E2, E3 tuning, E3 gap (Sonnet replay), E4, E5, E6, E7 in sequence; then generates figures and writes `results/run_log.json`.

It does not invoke E1. It also does not invoke `experiments/report.py`.

### `experiments/common.py`

- Sets `RESULTS = ROOT / "results"`.
- `save(name, obj)` writes directly to `results/<name>.json`.
- Creates the historical results directory if absent.
- Loads processed registry, tasks, recorded LLM outputs and model profiles.

This means each experiment's default output target is the historical results directory, not an isolated run bundle.

### Individual experiment outputs

- E0: `results/e0_registry.json`
- E2: `results/e2_eligibility.json`
- E3 tune: `results/e3_tune.json`
- E3 gap: `results/e3_gap_<model>.json`
- E4: `results/e4_injection.json` (also reads `results/e3_gap_sonnet.json`)
- E5: `results/e5_synthetic.json`
- E6: `results/e6_ablations.json`
- E7: `results/e7_scalability.json`
- Plot: overwrites six PNG files under `results/figures/`
- Run orchestrator: overwrites `results/run_log.json`
- Shell wrapper: overwrites `results/run_all.log`

### Report generation

`experiments/report.py` writes `docs/RESULTS.md` directly. This is a tracked manuscript-facing report and must be treated as historical/read-only during reproduction.

### Processed-data builder

`src/taas/data/registries.py` writes `data/processed/registry_merged.json`. This is a direct historical data overwrite risk.

## E0–E7 mapping and gaps

| ID | Current entry point | Inputs / dependencies | Existing output |
|---|---|---|---|
| E0 | `experiments/e0_registry.py` | processed registry, silver labels / realreg truth | `results/e0_registry.json` |
| E1 | **No dedicated E1 entry point found** | README mentions E1 real sandbox traces, but current experiment directory contains no E1 script | No separate E1 output found |
| E2 | `experiments/e2_eligibility.py` | raw registry, silver truth, simulated verifier/attack registry | `results/e2_eligibility.json` |
| E3 | `experiments/e3_tune.py`, `experiments/e3_gap.py` | processed tasks, prompts, replayed analyst outputs, model profiles | `results/e3_tune.json`, `results/e3_gap_sonnet.json` |
| E4 | `experiments/e4_injection.py` | E3 Sonnet result, task/registry data, simulated injected actions | `results/e4_injection.json` |
| E5 | `experiments/e5_synthetic.py` | synthetic typed registries/tasks and composition algorithms | `results/e5_synthetic.json` |
| E6 | `experiments/e6_ablations.py` | MCPToolBench++/LiveMCPBench tasks, recorded LLM outputs, retrieval and profile code | `results/e6_ablations.json` |
| E7 | `experiments/e7_scalability.py` | synthetic registry sizes, bitmap/index and maintenance implementation | `results/e7_scalability.json` |

E1 is a concrete mismatch: README describes no MCP server executed, while E0 docstring refers to E1 real sandbox traces; the experiment runner has no E1. This should be resolved in the design and paper before treating E1 as a reproducible experiment.

## Additional reproducibility and scientific observations

1. README quick-start lists tests, `experiments/run_all.py`, `experiments/report.py`, then `reproduce.sh`; the shell script itself installs dependencies, runs tests, rebuilds processed data and runs experiments, but does not regenerate `docs/RESULTS.md`.
2. The current output path design writes directly into historical `results/`; a safe wrapper or configurable output root is required before executing E0–E7.
3. The current README states that no MCP server was executed, gold-tool recall is not end-to-end task success, verifier FAR is simulated, and labels are LLM silver labels. Those limitations must remain attached to any reproduced claims.
4. README states 40 tests. This was not verified here because dependencies and test suite were not run.
5. The current E0 script compares registry statistics with hard-coded paper reference values; this is a consistency check, not independent ground truth validation.

## Gate 0 decision

**Remote static inspection: PASS WITH CONDITIONS. Local baseline capture: BLOCKED. Experiment execution: NOT STARTED.**

Before any E0–E7 run:
- obtain a local clone and install/use Codex CLI;
- record local branch, HEAD, dirty state and remotes;
- compute SHA-256 for every historical file under `data/` and `results/`;
- inspect all scripts on the exact local commit;
- implement or use a non-invasive output-root override so all new outputs go to unique `results/runs/<run_id>/`;
- preserve historical processed registry, result JSON, figures, logs and `docs/RESULTS.md`;
- resolve the E1 definition and its status;
- run tests in a disposable environment before long experiments.

No source code, dataset, historical result, or manuscript file was modified by this inspection.
