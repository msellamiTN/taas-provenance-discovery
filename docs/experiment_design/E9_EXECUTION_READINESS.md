# E9 execution readiness snapshot

> **Protocol gate:** E9 is not released for confirmatory execution until the upstream E1, E2, E3 and E12 prerequisite artifacts are accepted. See [dataset-led E1–E22 execution sequence](DATASET_LED_EXECUTION_SEQUENCE.md). E9 adapters and export tests may be validated before that gate; they are not benchmark results.

**Snapshot date:** 2026-11-07  
**Branch:** \`feature/pamcp-publication-visualization-v1\`

## Current status

The E9 figure contracts, evaluator-separated metric exporter and test fixtures are implemented. E9 has **not** been executed as a definitive benchmark. The test suite validates software behavior with isolated fixtures; fixture values are not experimental observations.

## Data inventory

| Input / artifact | Current repository state | Consequence |
|---|---|---|
| LiveMCPBench tools and annotations | Present under \`data/raw/livemcpbench/\`; source revision recorded in \`data/raw/SOURCES.txt\` | Available for source-specific identity and task-sequence diagnostics |
| LiveMCPBench independently adjudicated acceptable tool sets | Not present as a separate evaluator artifact | Annotated tool sequences remain positive-trace diagnostics, not exhaustive set gold |
| MCP-Atlas public parquet | Adapter exists; raw parquet snapshot is not present | Pin and acquire the 500-task public release before diagnostics |
| MCPVerse v1.1 CSV | Adapter exists; pinned CSV is not present | Can support a separate single-target diagnostic, not multi-tool complete-set gold |
| E9 GoalSpecs | No frozen E9 task-level GoalSpec package is present | Do not derive subgoals from evaluator labels or annotator traces |
| Independent typed contracts / equivalence oracle | No E9-specific frozen contract/oracle package is present | CMTF and ToolScope results remain blocked until their independent inputs exist |
| E9 rankings / run manifest | No \`results/definitive/E9/<run-id>/\` exists | No definitive method ranking or primary set metric is available |

## Primary metric gate

E9-F1/F2/F3 are generated only from evaluator records whose \`reference_semantics\` is either:

- \`independently_adjudicated_acceptable_sets\`
- \`benchmark_native_acceptable_sets\`

The pinned LiveMCPBench paper describes proposer-completed tasks and validator-scrutinized toolchains. The strict subset of 64 tasks with uniquely resolved tool IDs and matching declared tool counts is admissible as one benchmark-native successful reference set per task. It does not establish that the reference is the only valid chain. The 3 count-mismatch and 28 ambiguous/unresolved tasks are excluded and retained in the preparation audit. MCP-Atlas trajectories remain diagnostics because the public schema supplies a successful trace, not exhaustive acceptable-set gold. MCPVerse's annotated tool field is single-target, not multi-tool complete-set ground truth.

The exporter refuses:
- evaluator labels in discovery rankings;
- predicted tools outside per-task visibility;
- unregistered baseline IDs or an unexecuted Full PaMCP primary configuration;
- acceptable-set members outside the task visibility set;
- confidence intervals with fewer than two independent units.

## Available implementation

- [E9 execution runbook](experiment_design/E9_EXECUTION_RUNBOOK.md)
- [E9 figure exporter](../experiments/export_e9_figures.py)
- [E9 exporter/rendering tests](../tests/test_e9_figure_export.py)
- [E9 plot contracts](experiment_design/pamcp_plot_plan_v1.json)

## Run interface

Once a run has separately materialized discovery rankings and evaluator references:

\`\`\`bash
python experiments/export_e9_figures.py \\
  --run-dir results/definitive/E9/<run-id> \\
  --output-dir results/visualization/data \\
  --bootstrap-resamples 5000 \\
  --seed 20261107

python experiments/plot_results.py validate-data --experiment E9
python experiments/plot_results.py render --experiment E9
\`\`\`

A trace-only run may generate \`E9_TRACE_DIAGNOSTICS.csv\` and an export manifest with no primary figures. This is an intentional scientifically valid partial result, not a failure and not evidence of set completeness.

## Baseline assignment reconciliation

The frozen E9 experiment object assigns seven baseline IDs: `rag_mcp`, `mcp_zero`, `per_subtask`, `colt_adapted`, `toolscope_adapted`, `cmtf_adapted` and `all_tools`. The broader baseline catalogue and Core Protocol v2 also describe BM25 and Dense LSA as E9-capable, but E9's frozen experiment-specific `baseline_ids` omits them. The current exporter follows the experiment-specific assignment and rejects unregistered methods. Add BM25/Dense LSA only through an explicit protocol amendment, not by changing the run manifest.

## Required next research inputs

1. Run `python experiments/prepare_e9_livemcpbench.py --output results/definitive/E9/prepared-livemcpbench-v1` to materialize the strict 64-task LiveMCPBench candidate/task/reference package and the exclusion audit. This is dataset preparation, not a method run.
2. Freeze independently authored task GoalSpecs on a development/adjudication split, without evaluator qrels or test trajectories leaking into discovery.
3. Establish task-to-tool identity mappings against the pinned candidate registry and review all 95 source-resolution audit rows.
4. Supply independently sourced typed contracts for CMTF and an equivalence oracle for ToolScope, or record these methods as blocked.
5. Freeze GoalSpecs and all method parameters; run Full PaMCP and each feasible registered baseline with identical candidate visibility and frozen cutoffs.
6. Save per-task rankings before opening evaluator references; then run the E9 exporter and retain per-task metric rows for paired analyses.

E9 remains partial until the frozen baseline/source matrix and reference gates are satisfied. A rendered chart or passing unit test never changes that status.
