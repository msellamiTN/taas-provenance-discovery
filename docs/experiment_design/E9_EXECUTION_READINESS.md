# E9 execution readiness snapshot

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

LiveMCPBench tool sequences and MCP-Atlas trajectories are positive traces; MCPVerse's annotated tool field is single-target. They remain separate diagnostics unless an independent adjudication supplies valid acceptable-set references.

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

## Required next research inputs

1. Freeze independently authored task GoalSpecs on a development/adjudication split, without evaluator qrels or test trajectories leaking into discovery.
2. Establish task-to-tool identity mappings against the pinned candidate registry.
3. Adjudicate one or more acceptable tool sets per primary test task, with provenance, source revision and independent-unit IDs.
4. Supply independently sourced typed contracts for CMTF and an equivalence oracle for ToolScope, or record these methods as blocked.
5. Run Full PaMCP and each feasible registered baseline with identical candidate visibility and frozen cutoffs.
6. Save per-task rankings before opening evaluator references; then run the E9 exporter and retain per-task metric rows for paired analyses.

E9 remains partial until the frozen baseline/source matrix and reference gates are satisfied. A rendered chart or passing unit test never changes that status.
