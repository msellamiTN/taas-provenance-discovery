# PaMCP publication visualization framework

## Scope and protocol boundary

This framework defines and renders the publication figures for the frozen PaMCP E1-E22 programme. It is a visualization layer only. It does **not** change experiment definitions, hypotheses, metrics, dataset assignments, baseline assignments, G/P/S semantics, factorial cells, or result status. It does not execute experiments or generate evaluator observations.

The machine-readable figure registry is:

- \`docs/experiment_design/pamcp_plot_plan_v1.json\` — 80 figure contracts across E1-E22.
- \`docs/experiment_design/pamcp_experiments_v1.json\` — frozen experimental protocol.
- \`docs/experiment_design/pamcp_baselines_v1.json\` — frozen method and baseline assignments.

The plot-plan validator checks that experiment order, metric lists and baseline references agree with the frozen protocol. It also checks the complete eight-cell E18 factorial design.

## Installation

Matplotlib is already a project dependency. Install the optional tabular dependency and test tools:

\`\`\`bash
pip install -e ".[visualization,test]"
\`\`\`

## Commands

Run from the repository root.

### 1. Validate the plot registry

\`\`\`bash
python experiments/plot_results.py validate
\`\`\`

Expected structure: 22 experiments and 80 figure contracts. This validates metadata only; it does not claim that experiments have run.

### 2. Create input templates

\`\`\`bash
python experiments/plot_results.py init-templates
\`\`\`

This creates one header-only CSV per figure under \`results/visualization/data/\`. It inserts **no data rows**. Populate these files from the corresponding validated experiment result artifacts.

To recreate templates deliberately:

\`\`\`bash
python experiments/plot_results.py init-templates --overwrite
\`\`\`

Warning: \`--overwrite\` replaces existing CSV contents. Back up populated inputs first.

### 3. Validate an experiment's data

\`\`\`bash
python experiments/plot_results.py validate-data --experiment E8 --strict
\`\`\`

Or validate every supplied CSV:

\`\`\`bash
python experiments/plot_results.py validate-data --strict
\`\`\`

Validation checks required columns, missing values, finite numeric fields, interval ordering, requested facet columns, non-negative flow/count values and adjusted p-value domain. A header-only template is not a valid result file.

### 4. Render figures

\`\`\`bash
python experiments/plot_results.py render --experiment E8 --strict
\`\`\`

Render all experiments only after their data packages are populated:

\`\`\`bash
python experiments/plot_results.py render --strict
\`\`\`

Default outputs are vector PDF and SVG plus 300-DPI PNG under \`results/visualization/figures/\`. The framework writes \`figure_manifest.json\` with the plot-plan hash, each source CSV hash, row count and output paths.

For a quick inspection, select only one format:

\`\`\`bash
python experiments/plot_results.py render --experiment E8 --formats png --dpi 160
\`\`\`

Without \`--strict\`, absent data files are skipped and reported; malformed or empty files are still reported as errors. With \`--strict\`, any missing or invalid figure input fails the render.

## CSV contracts

Each figure contract declares its exact required columns in the JSON registry. The most common layouts are:

| Chart family | Required data layout |
|---|---|
| Forest / grouped dot | category, value, optionally series; forest additionally requires ci_low and ci_high |
| Heatmap | x category, y category, value |
| Confusion matrix | actual, predicted, count |
| Dose-response / line | x value, value; optional series and ci_low/ci_high |
| Pareto / scatter | x, y; optional series, label and bubble-size field |
| Dumbbell | category, reference, candidate |
| Stacked horizontal | category, segment, value |
| Violin | group, value (one row per observational unit) |
| Alluvial | source, target, value |
| Calibration | claimed, measured |
| Rankogram | rank, probability, series |
| Significance scatter | effect, adjusted_p |

Examples of headers (not data):

\`\`\`csv
category,value,ci_low,ci_high,series
\`\`\`

\`\`\`csv
util_at_5,exp_at_5,series,eligible_share,benchmark
\`\`\`

\`\`\`csv
metric,configuration,value
\`\`\`

Use the exact column names in the plot registry; do not rename them ad hoc. Optional \`n\` values may be included to preserve group sample sizes in source artifacts. The source CSV and its hash are retained in the figure manifest.

## Scientific and statistical requirements

1. Use only observations from the matching experiment, dataset release, split, run ID and protocol version.
2. For percentages/rates formatted as percentages, store proportions on the 0-1 scale (for example, 0.74 means 74%). The chart axis formatter then displays percent values.
3. \`ci_low\` and \`ci_high\` must be the confidence limits for the plotted estimand, computed using the experiment's statistical contract. Do not place standard errors or standard deviations in those columns.
4. Preserve the protocol's declared resampling unit. For matched tasks, preserve pairing when computing effect estimates and intervals.
5. Do not pool ToolRet, MCP-Atlas, MCP-native benchmarks, injection datasets or domain-specific policy datasets unless the protocol explicitly defines a pooled estimand. Use separate facets or files.
6. E18 must include all eight G×P×S configurations. Main effects and interactions must be estimated from all eight cells; the leave-one-out contrasts alone are not an interaction analysis.
7. In E22, keep confirmatory Holm-adjusted tests distinct from the designated exploratory BH family. Adjusted p-values must be in (0, 1] for the log-scale significance plot.
8. Do not plot legacy E0-E7 exploratory results as definitive E1-E22 results. Do not fill missing observations with zero or fabricate illustrative rows.
9. A chart is not evidence of execution. Experiment status and run manifests remain controlled by the experimental runner/evaluator, not by this visualization framework.

## Chart families

The registry uses publication-oriented chart forms rather than defaulting to line charts and histograms:

- Forest plots and grouped dot/estimation plots with confidence intervals.
- Pareto scatter plots for security/utility and quality/cost trade-offs.
- Annotated heatmaps and confusion matrices.
- Dumbbell plots for paired before/after comparisons.
- Dose-response and interaction plots.
- Violin distributions for task-level measurements.
- Alluvial transition diagrams for state, evidence and refinement flows.
- Calibration diagrams, rankograms and log-log scalability plots.
- Stacked horizontal bars for failure composition.

Matplotlib renders static outputs. The renderer uses a non-interactive backend and does not require a notebook. Interactive TaaS Studio charts can be added as a separate view over the same normalized result exports; they must not recompute evaluation metrics.

## Troubleshooting

- **Missing CSV**: run \`init-templates\`, then export the relevant metrics from the validated experiment result package.
- **Header-only CSV**: populate it with actual observations; templates are intentionally empty.
- **Missing facet field**: the plot contract requires a facet column for that figure. Do not remove the facet to hide benchmark or method distinctions.
- **Missing CI columns**: forest plots require \`ci_low\` and \`ci_high\`. Compute intervals from the registered resampling unit; do not use arbitrary error bars.
- **No figure created**: inspect the CLI error and \`figure_manifest.json\`. Strict mode stops on missing or invalid inputs.
- **Confusion matrix normalization**: rows correspond to the reference/actual class and are normalized within each actual class when requested.
