# E8 execution readiness snapshot

> **Protocol gate:** E8 is not released for confirmatory execution until the upstream E1, E2, E3 and E12 prerequisite artifacts are accepted. See [dataset-led E1–E22 execution sequence](experiment_design/DATASET_LED_EXECUTION_SEQUENCE.md). E8 adapters and export tests may be validated before that gate; they are not benchmark results.

**Snapshot date:** 2026-11-07  
**Branch:** `feature/pamcp-publication-visualization-v1`  
**Snapshot commit:** `6dc5aed19d980f10b1b8328a0f141822731d73a2`

## Status

The E8 execution, provenance export and publication-plotting pipeline is implemented and regression-tested. A new definitive E8 benchmark run has **not** yet been executed from this repository snapshot. The result directory and required prepared source snapshots are absent.

| Required artifact | Snapshot finding | Consequence |
|---|---|---|
| `data/raw/mcptoolbenchpp/` | Contains only the source `LICENSE`; the six pinned category JSON files are absent | Run the hash-verifying MCPToolBench++ preparation step |
| `data/processed/toolret/` | Directory absent | Resolve and prepare the independent pinned ToolRet query/tool revisions |
| `results/definitive/E8/` | Directory absent | No definitive E8 run manifest, per-task metrics or ranking caches are available |
| `results/visualization/data/E8-F1.csv` | Not present | No new E8 comparison figure input exists |
| `results/visualization/data/E8-F4.csv` | Not present | No new category-stratified E8 figure input exists |

## Existing ToolRet aggregate artifact — not a substitute

The repository contains `artifacts/multibenchmark/toolret_baselines/aggregate_metrics.json` and `aggregate_metrics.csv`. The associated README reports 7,960 evaluated queries for BM25, TF-IDF and a deterministic random sanity baseline. It identifies the source as a previous completed Colab run and states that no ranking or dataset acquisition was repeated for that publication bundle.

This historical aggregate is useful for provenance and historical description only. It has aggregate metrics, not the per-task observations and independent-unit identifiers required by the current E8 exporter. Its README explicitly says it has no confidence intervals. Therefore:

- Do not copy these rows into the definitive E8-F1/E8-F4 inputs.
- Do not create confidence intervals from the aggregate means and sample size.
- Do not pool it with a new E8 run or claim it represents the amended E8 ToolRet campaign.
- Retain it as a separate historical artifact.

## Execution route

Use the [Drive-backed E8 Colab notebook](../experiments/colab/E8_Retrieval_Campaign.ipynb) on a CUDA GPU runtime. It mounts persistent storage at `MyDrive/PaMCP_E8`, prepares pinned sources, resolves immutable model revisions, executes the immutable E8 run, exports per-task metrics with cluster identifiers, and renders only the E8 figures whose data and uncertainty conditions are met.

The equivalent repository-root launcher is:

```bash
E8_DEVICE=cuda bash experiments/run_e8_and_plot.sh
```

The launcher uses a unique run ID and records the source revisions, model revisions, configuration, input hashes, executed baseline IDs, exclusions, paired tests and run status. Do not reuse a finalized run ID. Keep the run directory and ZIP artifact intact.

## Expected partial-result behaviour

A valid E8 campaign may remain `partial`. This is not a software failure. The run manifest must explicitly record registered baseline adapters or source conditions that were blocked/not comparable. The exporter:

- includes only registered E8 methods with observed per-task metrics;
- excludes supplementary unregistered controls from primary figures;
- computes 95% percentile-bootstrap intervals from the correct independent units (tasks for ToolRet; target-server clusters for MCPToolBench++);
- exports E8-F1 and E8-F4 only when their input and uncertainty requirements are met;
- leaves E8-F2 unavailable until B1/B1m source conditions are verified;
- leaves E8-F3 unavailable until the predeclared distractor-count sweep is executed.

The experiment status is never inferred from the presence of a rendered chart. Read `results/definitive/E8/<run-id>/MANIFEST.json` and `results/visualization/data/E8_EXPORT_MANIFEST.json` before interpreting the figures.

## Software verification

The GitHub Actions run [42419848968](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42419848968) passed:

- E1-E22 plot-plan validation;
- E8 launcher syntax check;
- E8 Colab notebook JSON validation;
- plotting and E8 regression tests: **40 passed**.

The E8 exporter-to-renderer integration test uses isolated test fixtures. It validates the software path; those fixture values are not experimental observations and are not stored in `results/visualization/data/`.
