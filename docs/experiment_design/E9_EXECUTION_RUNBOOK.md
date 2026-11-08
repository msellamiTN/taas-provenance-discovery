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

The LiveMCPBench paper describes a two-stage task curation process: proposers completed tasks by interacting with the toolset and annotated the toolchain; validators scrutinized the task and corresponding toolchain invocations. The protocol review explicitly defines the E9 evaluable set as the **94 of 95 tasks with at least one resolvable gold tool**. For ambiguous tool names, any candidate server::tool identity is accepted. Each task's annotation remains one benchmark-native successful toolchain reference, not an exhaustive list of all possible valid solutions.

The protocol-aligned preparation script, `experiments/prepare_e9_livemcpbench.py`, uses the pinned `LiveMCPTool` candidate registry only (525 tools / 69 servers). The campaign runner independently enforces the exact pinned source revision `36a51a1065dda49c1e503b87edf33a1e0b331a74`, this LiveMCPTool-only view, 525 tools/69 servers, and the 94-of-95 task denominator before method execution. It produces 94 primary tasks from the 95-task public set: 222 unique-identity tool mentions, 29 ambiguous mentions (each expanded to all candidate identities, any of which counts), and 5 unresolved mentions (retained in the audit and omitted from the resolvable reference set). Four tasks have a declared tool-count mismatch; this is recorded but does not independently exclude a task. Only the one task with no resolvable gold tool is excluded. The 94 accepted references are tagged `benchmark_native_acceptable_sets`; the complete-set metric is coverage of the documented successful reference set with the protocol's any-candidate rule, not proof that no alternative task solution exists.

Do not use the older registry helper's ambiguous-name composite IDs as stable tool IDs. Preserve each ambiguous annotation as a candidate-choice list and expand those choices into acceptable reference-set alternatives.

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

## Protocol decomposition and candidate budgets

The original E9 protocol preregisters three decomposition conditions:

| Decomposition | Operational input to retrieval |
|---|---|
| \`none\` | The original user request is passed as one unsegmented goal/query. |
| \`clause_splitter\` | A deterministic clause-splitter output is frozen without access to evaluator references. Preserve the source prompt, splitter version and source-code hash. |
| \`llm_analyst\` | An independently versioned analyst produces a structured GoalSpec. Freeze model ID/revision, prompt version, decoding settings, usage, raw response and their hashes before evaluation. |

The current full evaluation protocol preregisters **k = 1, 3, 5, 10, 20**. Execute every value as a separate candidate-budget condition. Every discovery row must include \`decomposition\` and \`ranking_k\`; the unique observation key is benchmark × task × method × decomposition × k. Do not derive lower k conditions by truncating a single k=20 output.

For retrieval comparators, save the ordered top-k tools. For Full PaMCP and PaMCP-NoBackwardClosure, save the actual certified selected toolkit returned at that candidate budget; it may contain more than k tools because a multi-goal composition can require multiple tools. Do not truncate the composed toolkit after selection. Preserve the empty-set/abstention state as a zero-coverage task result.

The figures facet by benchmark × decomposition, and E9-F3/E9-F4 additionally facet by k. Never average decomposition conditions or candidate budgets together.

The \`llm_analyst\` condition is not executable until a pinned model and accepted analyst outputs are available. Missing analyst outputs are recorded as blocked; do not substitute the clause splitter or an LLM output created after evaluator access.

## Metrics

For predicted top-k set \(P_k\) and acceptable reference alternatives \(\mathcal{A}=\{A_1,\ldots,A_m\}\):

1. Select one reference alternative by maximum Jaccard similarity. Ties are resolved deterministically by sorted tool IDs.
2. Set precision is \(|P_k\cap A^*|/|P_k|\).
3. Group recall@k is \(|P_k\cap A^*|/|A^*|\).
4. Complete-set indicator is \(1\) iff there exists any \(A_i\in\mathcal{A}\) such that \(A_i\subseteq P_k\).
5. Complete-set share is the mean complete-set indicator over tasks with an admissible reference.

The same selected reference is used for precision and recall. This avoids selecting a different alternative set for each side of the precision/recall point. An empty prediction set has precision=0, recall=0 and complete-set indicator=0; report coverage/abstention separately. Tasks with no admissible acceptable-set reference are excluded from these metrics, not scored as zero.

Bootstrap intervals use the evaluator's \`independent_unit_id\` (task or a declared cluster). A group with fewer than two independent units receives no CI and is listed in the export manifest. Paired method comparisons use the same independent-unit definition: task differences are cluster-bootstrapped and sign-flipped at cluster level, while the reported mean difference is task-weighted. Paired rows retain both common-task and independent-unit counts. The point estimator is the task-weighted mean paired difference. Exact sign-flip enumeration is used when there are at most 16 independent units; otherwise the registered Monte Carlo sign-flip budget is used. The export manifest records the cluster-level resampling unit, estimator and exact-test threshold. A paired comparison with fewer than two independent units is marked insufficient rather than assigned a p-value.

## E9 comparator set

The comparator mapping follows the explicit E9 comparison table in the original Experimental Protocol and the k-grid update in the 5 November TSC Full v1 protocol. The machine-readable E9 baseline catalogue now carries the same experiment-specific comparator IDs.

| Method | E9 role | Execution condition |
|---|---|---|
| Full PaMCP | Separate primary configuration | Full backward closure, accepted contracts, accepted E12 profile, policy and certificate path |
| COLT | External comparator | Retrained/constructed from the MCPToolBench++ development split; query scenes are derived from server membership and mapped through an explicit tool crosswalk into the LiveMCPTool candidate pool |
| MCP-Zero | External comparator | Official iterative LLM active-request loop and request protocol are required; the repository's single-pass adapter is not accepted as a substitute |
| ToolScope | External comparator | Independent accepted equivalence oracle is required to report merge precision, recall and false-equivalence |
| CMTF | External comparator | Uses the same accepted common typed contracts and frozen GoalSpecs as PaMCP |
| PaMCP without backward closure | Internal ablation comparator | Same PaMCP pipeline and settings as Full PaMCP; change only backward-closure depth to zero |

\`per_subtask\` is independent per-goal retrieval followed by union; it is not the PaMCP-NoBackwardClosure ablation. \`rag_mcp\` and \`all_tools\` may be useful supplementary controls elsewhere in the study, but are not E9 confirmatory comparators under the explicit E9 comparator table. They must not be inserted into E9's confirmatory baseline list without a versioned protocol amendment.

The ToolScope oracle loader rejects duplicate unordered pairs (including reversed duplicates), contradictory labels, malformed/out-of-pool IDs, and an oracle missing either positive or negative examples. Its merge metrics are not emitted from a contradictory or one-class oracle.

The current repository implementation maturity is disclosed in each run manifest. MCP-Zero remains blocked until the official active-request loop is implemented. COLT remains blocked unless the accepted MCPToolBench++ dev scene bundle and crosswalk validate. ToolScope remains blocked until its independent equivalence oracle is accepted. CMTF is executable only with the accepted common typed-contract bundle. None may be silently replaced by a similarly named method.

## Executable E9 runner and accepted inputs

The campaign runner is \`experiments/e9_retrieval_campaign.py\`. Before loading discovery inputs, it verifies \`SHA256SUMS.json\` against the exact extracted package inventory and all discovery-side files. It confirms the evaluator-reference path is present and captures its expected digest without reading its bytes; only after discovery rankings are written and hashed does it hash and parse the evaluator references. It refuses to start unless the E1, E2, E3 and E12 prerequisites are accepted, SHA-256 verified, and the comparator-map approval is in place.

Required input package:

| Input | Acceptance contract |
|---|---|
| Release gate | schema_version=1.0.0, status=accepted; E1/E2/E3/E12 each have status=accepted, an artifact path, SHA-256 and acceptance ID |
| Comparator map | status=accepted; baseline IDs exactly match the frozen E9 experiment; separate Full_PaMCP primary ID; protocol document SHA-256 and approval record |
| GoalSpecs | 94 tasks × 3 decomposition conditions = 282 frozen JSONL records; prompt hash, explicit no-evaluator-access flag and transformation provenance |
| Contract bundle | status=accepted; all 525 candidate tools are hash-bound to their definitions; no evaluator labels used; accepted E2 and E3 source-artifact hashes |
| Model profile | accepted E12 bundle with model ID/revision and measured ModelProfile class curves |
| Policy bundle | accepted and versioned E9 policy artifact |
| Composer config | approved E9 ComposerConfig with base K=20 and positive backward-closure depth; frozen refinement depth |
| Encoder bundle | accepted, materialized local SentenceTransformers snapshot; model ID/revision and package version pinned; SHA-256 manifest covers the exact complete file inventory (no unlisted files, traversal paths or symlinks) |
| COLT scene bundle | accepted MCPToolBench++ development split; query-to-server memberships; server-derived scenes; source-tool-to-LiveMCPTool crosswalk and SHA-256 |
| ToolScope oracle | independently accepted positive and negative tool-equivalence pairs; every unordered pair is unique, labels are non-conflicting, both classes are represented, and no E9 evaluator labels are used |

The runner uses a local-only SentenceTransformers model snapshot; it sets offline flags and does not silently download or substitute an encoder. The encoder bundle must hash every regular file in the materialized snapshot, with exact inventory equality; symlinks and path traversal are rejected so tokenizer/config/weight changes cannot be hidden outside the manifest. It does not synthesize GoalSpecs, contracts, effects, model profiles, training scenes or equivalence labels.

Launch command after all mandatory input artifacts have been accepted:

    pip install -e ".[retrieval,experiment]"

    python experiments/e9_retrieval_campaign.py \
      --prepared-dir results/definitive/E9/prepared-livemcpbench-v2 \
      --release-gate artifacts/e9/release_gate.json \
      --comparator-map artifacts/e9/comparator_map.json \
      --goal-specs artifacts/e9/goal_specs_94x3.jsonl \
      --contract-bundle artifacts/e9/contracts_525.json \
      --model-profile artifacts/e12/accepted_model_profile.json \
      --policy-bundle artifacts/e9/policy.json \
      --composer-config artifacts/e9/composer_config.json \
      --encoder-bundle artifacts/e9/encoder_bundle.json \
      --training-scenes artifacts/e9/colt_dev_server_scenes.json \
      --equivalence-oracle artifacts/e9/tool_equivalence_oracle.json \
      --output-dir results/definitive/E9/e9-livemcpbench-run-001 \
      --run-id e9-livemcpbench-run-001 \
      --device cuda

The COLT scene bundle and ToolScope equivalence oracle may be omitted only when those methods are explicitly recorded as blocked; the resulting E9 run remains partial. MCP-Zero is also marked blocked until its official iterative active-request loop is implemented.

For every task × method × decomposition × k condition, the runner emits one prediction row. Full PaMCP and PaMCP-NoBackwardClosure each run with the same accepted configuration; the ablation changes only backward-closure depth from its accepted positive value to zero. The other candidate-budget values are applied independently to each run. A selected PaMCP toolkit is recorded as returned; it is not truncated to k after composition.

The runner's output is \`results/definitive/E9/<run-id>/MANIFEST.json\`, \`discovery/rankings.jsonl\` and the copied evaluator references. The manifest remains \`partial\` whenever any registered comparator is blocked or incomplete.

## Export and render

After a definitive or partial E9 run has materialized discovery predictions and evaluator references:

    python experiments/export_e9_figures.py \
      --run-dir results/definitive/E9/<run-id> \
      --output-dir results/visualization/data \
      --bootstrap-resamples 10000 \
      --sign-flip-resamples 100000 \
      --seed 20261108

    python experiments/plot_results.py validate-data --experiment E9
    python experiments/plot_results.py render --experiment E9

Outputs:

- \`E9_per_task_metrics.csv\` — task-level Group Recall@k, set precision, complete-set indicator, coverage and predicted/reference set sizes.
- \`E9-F1.csv\` — Group Recall@k with 95% paired-task/cluster bootstrap CIs.
- \`E9-F2.csv\` — set precision versus Group Recall@k; bubble size represents complete-set share.
- \`E9-F3.csv\` — complete-set share by task group, method, decomposition and k.
- \`E9-F4.csv\` — task-level retrieved-toolkit size distribution by method, decomposition and k.
- \`E9_PAIRED_TESTS.csv\` — Full PaMCP versus each registered E9 comparator on matched task IDs; paired mean difference, 95% bootstrap interval, paired sign-flip p-value and Holm adjustment across available tests.
- \`E9_TRACE_DIAGNOSTICS.csv\` — trace-only coverage; never merged into primary set-quality metrics.
- \`E9_EXPORT_MANIFEST.json\` — source hashes, run status, reference semantics, exclusions, confidence intervals, paired-test family and figure availability.

A partial E9 run can render partial figures. Missing methods are recorded as blocked; no missing scores are imputed. A rendered figure or passing unit test does not change the experiment status.

## Current readiness boundary

The repository contains the pinned LiveMCPBench snapshot, a protocol-aligned 94-task preparer, an E9 retrieval campaign runner and an evaluator-separated metric exporter. The runner has not yet produced a definitive run: no accepted E1/E2/E3/E12 release gate, comparator approval, frozen 282-row GoalSpec matrix, accepted 525-tool contract bundle, E12 profile, policy/config/encoder package, COLT training scenes or ToolScope equivalence oracle has been supplied. Therefore E9 method comparisons and performance results are not yet available.
