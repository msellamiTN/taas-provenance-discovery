# E9 — Multi-tool retrieval and set-quality runbook

## Scope

E9 evaluates whether discovery methods retrieve tool sets that cover an independently specified multi-goal task. It is a **set-retrieval** experiment, not an execution-success, effect-correctness, security or runtime-assurance experiment.

The frozen experiment definition and baseline assignment remain authoritative:

- \`docs/experiment_design/pamcp_experiments_v1.json\` — E9 datasets, metrics and registered baseline IDs.
- \`docs/experiment_design/pamcp_baselines_v1.json\` — method semantics and implementation maturity.
- \`docs/experiment_design/pamcp_plot_plan_v1.json\` — E9-F1, E9-F2 and E9-F3 figure contracts.

E9's separate primary configuration is \`Full_PaMCP\`. The exporter permits it only when the run manifest explicitly states \`primary_configuration_executed=true\` and identifies \`Full_PaMCP\`. The registered baseline IDs remain unchanged.

## Dataset semantics and admissible references

### LiveMCPBench

The repository contains \`data/raw/livemcpbench/tools.json\` and \`all_annotations.json\`. Annotator metadata includes a task step sequence and a list of tools associated with that sequence.

That annotation is a positive reference trace/sequence. It does not prove that the list is exhaustive, that every named tool identity is unambiguous, or that no alternative valid tool set exists. The existing registry helper can collapse ambiguous names to a composite string; that mapping must not be used as a stable tool ID in a definitive E9 run without explicit identity resolution.

Use LiveMCPBench traces for **trace-coverage diagnostics** unless independent adjudication establishes one or more acceptable tool sets for the task.

### MCP-Atlas public

The public release contains 500 tasks. \`ENABLED_TOOLS\` is the per-task candidate visibility set. \`GTFA_CLAIMS\` is an answer-claim reference, and \`TRAJECTORY\` is a successful trajectory diagnostic.

A trajectory is not exhaustive acceptable-set gold. Keep it in the trace diagnostic track. Do not infer alternative tool sets or complete-set correctness from claims alone.

### MCPVerse time-invariant v1.1

The pinned v1.1 CSV records a task question and an annotated MCP/tool reference. It does not provide a complete tool schema or multi-tool acceptable-set collection. Keep it as a separate single-target retrieval diagnostic; do not promote its single tool label to a multi-tool acceptable set.

### Primary metric eligibility

The E9 primary figures require one of these evaluator reference classes:

- \`independently_adjudicated_acceptable_sets\`
- \`benchmark_native_acceptable_sets\`

Each task reference must contain a non-empty list of non-empty acceptable tool sets, and every referenced tool must belong to that task's declared visible candidate pool. Missing references remain missing; no value is imputed.

These reference semantics are diagnostic-only and are excluded from primary E9 metrics:

- \`annotated_trace_only\`
- \`positive_trace_only\`
- \`mcp_atlas_trajectory_diagnostic\`

The exporter may write \`E9_TRACE_DIAGNOSTICS.csv\` for positive-trace coverage, but it will not use those rows in E9-F1/F2/F3.

## Discovery/evaluator separation

Predictions must be generated and frozen before evaluator references are loaded.

Required run layout:

\`\`\`text
results/definitive/E9/<run-id>/
├── MANIFEST.json
├── discovery/
│   └── rankings.jsonl
└── evaluator/
    └── task_references.jsonl
\`\`\`

Each discovery ranking record contains:

\`\`\`json
{
  "task_id": "stable-task-id",
  "benchmark": "benchmark-track-id",
  "baseline": "registered-method-id",
  "task_group": "declared-task-category",
  "ranked_tool_ids": ["server-a::tool-x", "server-b::tool-y"],
  "visible_tool_ids": ["server-a::tool-x", "server-b::tool-y", "server-c::tool-z"]
}
\`\`\`

Do not add qrels, acceptable sets, GTFA claims, trajectories, target tool IDs, answers or other evaluator fields to discovery records. The exporter rejects evaluator-field leakage and rejects any predicted tool outside the per-task visible candidate set.

Evaluator references are stored separately:

\`\`\`json
{
  "task_id": "stable-task-id",
  "benchmark": "benchmark-track-id",
  "reference_semantics": "independently_adjudicated_acceptable_sets",
  "acceptable_tool_sets": [
    ["server-a::tool-x", "server-b::tool-y"],
    ["server-a::tool-x", "server-c::tool-z"]
  ],
  "independent_unit_id": "task-or-server-cluster",
  "source_revision": "immutable-source-revision"
}
\`\`\`

For trace-only rows, use \`reference_semantics: "annotated_trace_only"\` (or the source-specific trace class) and \`reference_trace_tool_ids\`; do not populate primary acceptable sets from that trace.

## Metrics

For predicted top-k set \(P_k\) and acceptable reference alternatives \(\mathcal{A}=\{A_1,\ldots,A_m\}\):

1. Select one reference alternative by maximum Jaccard similarity. Ties are resolved deterministically by sorted tool IDs.
2. Set precision is \(|P_k\cap A^*|/|P_k|\).
3. Group recall@k is \(|P_k\cap A^*|/|A^*|\).
4. Complete-set indicator is \(1\) iff there exists any \(A_i\in\mathcal{A}\) such that \(A_i\subseteq P_k\).
5. Complete-set share is the mean complete-set indicator over tasks with an admissible reference.

The same selected reference is used for precision and recall. This avoids selecting a different alternative set for each side of the precision/recall point. An empty prediction set has precision=0, recall=0 and complete-set indicator=0; report coverage/abstention separately. Tasks with no admissible acceptable-set reference are excluded from these metrics, not scored as zero.

Bootstrap intervals use the evaluator's \`independent_unit_id\` (task or a declared cluster). A group with fewer than two independent units receives no CI and is listed in the export manifest.

## Registered methods and prerequisites

E9's frozen baselines are \`rag_mcp\`, \`mcp_zero\`, \`per_subtask\`, \`colt_adapted\`, \`toolscope_adapted\`, \`cmtf_adapted\` and \`all_tools\`.

- \`all_tools\`: expose the complete per-task visible candidate set.
- \`rag_mcp\`: clean-room global prompt/goal-view retrieval adaptation; disclose its configuration.
- \`mcp_zero\`: the current adapter is single-pass and does not reproduce the official active-request loop.
- \`per_subtask\`: requires independently authored/frozen GoalSpecs; do not derive goals from evaluator labels.
- \`colt_adapted\`: requires a declared training split and training-only query/tool scenes. Test/evaluator labels cannot create scenes.
- \`toolscope_adapted\`: requires an independent tool-equivalence oracle for merge precision/recall/false-equivalence; preserve original tool identities.
- \`cmtf_adapted\`: requires independently sourced typed precondition/effect contracts and frozen GoalSpecs.
- \`Full_PaMCP\`: run as the separately declared primary configuration; do not alias it to one of the baseline adapters.

Every method's exact adaptation, parameters, candidate visibility and run status must be in the manifest. A method that cannot run is recorded as blocked/not comparable, not replaced with a similarly named method.

## Export and render

After the run has materialized discovery rankings and evaluator references:

\`\`\`bash
python experiments/export_e9_figures.py \\
  --run-dir results/definitive/E9/<run-id> \\
  --output-dir results/visualization/data \\
  --bootstrap-resamples 5000 \\
  --seed 20261107

python experiments/plot_results.py validate-data --experiment E9
python experiments/plot_results.py render --experiment E9
\`\`\`

Outputs:

- \`E9_per_task_metrics.csv\` — task-level metrics retained for paired analyses.
- \`E9-F1.csv\` — group recall@k with bootstrap CIs, benchmark-faceted.
- \`E9-F2.csv\` — set precision vs group recall Pareto points; point labels identify methods and bubble size is complete-set share.
- \`E9-F3.csv\` — complete-set share by task group and method, benchmark-faceted.
- \`E9_TRACE_DIAGNOSTICS.csv\` — positive-trace coverage only; never included in primary figures.
- \`E9_EXPORT_MANIFEST.json\` — source hashes, run status, reference semantics, excluded rows, CIs and figure availability.

A partial E9 run can render partial figures. A rendered figure does not change the experiment status. Do not claim E9 complete while any preregistered source, baseline or reference-oracle gate remains blocked.

## Current readiness boundary

The repository contains the LiveMCPBench tool/annotation snapshot and an MCP-Atlas adapter. It does not yet contain an E9 definitive run manifest, frozen independently adjudicated multi-tool acceptable sets, or per-task rankings generated with frozen GoalSpecs/contracts. Therefore the exporter and figure path are implemented and testable, but no E9 scientific result is claimed by this implementation.
