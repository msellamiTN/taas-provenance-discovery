# E9 execution readiness snapshot

> **Protocol gate:** E9 is not released for confirmatory execution until the upstream E1, E2, E3 and E12 prerequisite artifacts are accepted. See [dataset-led E1–E22 execution sequence](DATASET_LED_EXECUTION_SEQUENCE.md). E9 adapters and export tests may be validated before that gate; they are not benchmark results.

**Snapshot date:** 2026-11-07  
**Branch:** \`feature/pamcp-publication-visualization-v1\`

## Current status

The E9 figure contracts, 94-task LiveMCPBench preparer, protocol-gated retrieval runner, evaluator-separated metric exporter and regression tests are implemented. E9 has **not** been executed as a definitive benchmark. The test suite validates software/data-preparation behavior with isolated fixtures; fixture values are not experimental observations.

## Data inventory

| Input / artifact | Current repository state | Consequence |
|---|---|---|
| LiveMCPBench tools and annotations | Pinned revision `36a51a1065dda49c1e503b87edf33a1e0b331a74`; 525 tools / 69 servers | Strict E9 preprocessor resolves task tool names against the LiveMCPTool-only candidate registry |
| LiveMCPBench benchmark-native successful reference chains | Protocol denominator is 94/95 tasks with at least one resolvable gold tool; 29 ambiguous mentions expand to all candidate identities, 5 unresolved mentions are audited, and 4 declared-count mismatches are flagged but not excluded | One validator-scrutinized successful chain per task with any-candidate identity alternatives; not exhaustive task-solution enumeration |
| MCP-Atlas public parquet | Adapter exists; raw parquet snapshot is not present | Pin and acquire the 500-task public release before diagnostics |
| MCPVerse v1.1 CSV | Adapter exists; pinned CSV is not present | Can support a separate single-target diagnostic, not multi-tool complete-set gold |
| E9 GoalSpecs | No frozen E9 task-level GoalSpec package is present | Do not derive subgoals from evaluator labels or annotator traces |
| Independent typed contracts / equivalence oracle | No E9-specific frozen contract/oracle package is present | CMTF and ToolScope results remain blocked until their independent inputs exist |
| E9 rankings / run manifest | No \`results/definitive/E9/<run-id>/\` exists | No definitive method ranking or primary set metric is available |

## Primary metric gate

E9-F1/F2/F3 are generated only from evaluator records whose \`reference_semantics\` is either:

- \`independently_adjudicated_acceptable_sets\`
- \`benchmark_native_acceptable_sets\`

The protocol-aligned preparation is implemented at `experiments/prepare_e9_livemcpbench.py`. It produces 94 discovery tasks/tools/visibility records separately from evaluator acceptable-set alternatives and a 95-row resolution audit. Ambiguous names expand to any candidate identity; five unresolved mentions remain disclosed, and only one task with no resolvable gold is excluded. MCP-Atlas trajectories remain diagnostic-only; MCPVerse's annotated tool field is single-target, not multi-tool complete-set ground truth.

The exporter refuses:
- evaluator labels in discovery rankings;
- predicted tools outside per-task visibility;
- unregistered baseline IDs or an unexecuted Full PaMCP primary configuration;
- acceptable-set members outside the task visibility set;
- confidence intervals with fewer than two independent units.

## Available implementation

- [LiveMCPBench E9 dataset preparer](../../experiments/prepare_e9_livemcpbench.py) (creates task/reference package, not method rankings)
- [E9 execution runbook](experiment_design/E9_EXECUTION_RUNBOOK.md)
- [E9 retrieval campaign runner](../../experiments/e9_retrieval_campaign.py)
- [E9 figure exporter](../../experiments/export_e9_figures.py)
- [E9 runner and protocol-gate tests](../../tests/test_e9_retrieval_campaign.py)
- [E9 exporter/rendering tests](../../tests/test_e9_figure_export.py)
- [E9 plot contracts](experiment_design/pamcp_plot_plan_v1.json)

## Run interface

Once the upstream release gate and all frozen input bundles are accepted, execute the runner as specified in E9_EXECUTION_RUNBOOK.md. It materializes rankings before reading evaluator references. The export/render commands below apply only after a definitive or partial E9 run manifest exists:

    python experiments/export_e9_figures.py \
      --run-dir results/definitive/E9/<run-id> \
      --output-dir results/visualization/data \
      --bootstrap-resamples 5000 \
      --seed 20261108

    python experiments/plot_results.py validate-data --experiment E9
    python experiments/plot_results.py render --experiment E9

A trace-only run may generate E9_TRACE_DIAGNOSTICS.csv and an export manifest with no primary figures. This is an intentional scientifically valid partial result, not a failure and not evidence of set completeness.

## Baseline assignment reconciliation

The frozen E9 experiment object assigns seven baseline IDs: rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted and all_tools. The broader baseline catalogue and Core Protocol v2 also describe BM25 and Dense LSA as E9-capable, but E9's frozen experiment-specific baseline_ids omits them. Add BM25/Dense LSA only through an explicit protocol amendment, not by changing the run manifest.

## Required next research inputs

1. Use the preserved 94-task LiveMCPBench dataset artifact from CI run 42422126446 (artifact 13593902899), or regenerate it from the pinned source.
2. Complete and accept E1, E2, E3 and E12; update the release gate with accepted artifact paths, SHA-256 values and acceptance IDs.
3. Approve a comparator map that resolves the original DOCX versus machine-readable E9 baseline mismatch without silently changing the preregistration.
4. Freeze all 282 GoalSpecs (94 tasks × three decomposition conditions), including raw LLM-analyst and clause-splitter artifact hashes.
5. Supply accepted hash-bound contracts for all 525 candidate definitions, a calibrated E12 model profile, accepted policy, composer configuration and local model encoder snapshot.
6. Supply training-only COLT scenes and an independently adjudicated ToolScope equivalence oracle; otherwise those baselines are marked blocked and the run remains partial.
7. Execute experiments/e9_retrieval_campaign.py; then run the E9 exporter and retain per-task metric rows for paired analyses.

E9 remains partial until the frozen baseline/source matrix and reference gates are satisfied. A rendered chart or passing unit test never changes that status.
