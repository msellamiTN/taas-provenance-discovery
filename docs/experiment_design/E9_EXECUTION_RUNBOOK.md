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

The protocol-aligned preparation script, `experiments/prepare_e9_livemcpbench.py`, uses the pinned `LiveMCPTool` candidate registry only (525 tools / 69 servers). It produces 94 primary tasks from the 95-task public set: 222 unique-identity tool mentions, 29 ambiguous mentions (each expanded to all candidate identities, any of which counts), and 5 unresolved mentions (retained in the audit and omitted from the resolvable reference set). Four tasks have a declared tool-count mismatch; this is recorded but does not independently exclude a task. Only the one task with no resolvable gold tool is excluded. The 94 accepted references are tagged `benchmark_native_acceptable_sets`; the complete-set metric is coverage of the documented successful reference set with the protocol's any-candidate rule, not proof that no alternative task solution exists.

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

## Protocol decomposition and ranking cutoffs

The original experiment specification preregisters three decomposition conditions and three cutoffs:

| Decomposition | Operational input to retrieval |
|---|---|
| \`none\` | The original user request is passed as one unsegmented goal/query. |
| \`clause_splitter\` | A deterministic clause-splitter output is frozen without access to evaluator references. Preserve the source prompt and splitter version. |
| \`llm_analyst\` | An independently versioned analyst produces a structured GoalSpec. Freeze model ID/revision, prompt version, decoding settings, usage and raw response before evaluation. |

Run all conditions at **k = 5, 10, 20**. Each ranking record must include its \`decomposition\` value and contain the top 20 ordered tool IDs; the exporter derives all three cutoffs from that single frozen ranking. The figure contracts use separate panels for benchmark × decomposition, and E9-F3 additionally facets by k. Never merge the three decomposition conditions into a single average.

The \`llm_analyst\` condition is not executable until a pinned model and accepted analyst outputs are available. Missing analyst outputs are recorded as blocked; do not substitute the clause splitter or an LLM output created after evaluator access.

## Metrics

For predicted top-k set \(P_k\) and acceptable reference alternatives \(\mathcal{A}=\{A_1,\ldots,A_m\}\):

1. Select one reference alternative by maximum Jaccard similarity. Ties are resolved deterministically by sorted tool IDs.
2. Set precision is \(|P_k\cap A^*|/|P_k|\).
3. Group recall@k is \(|P_k\cap A^*|/|A^*|\).
4. Complete-set indicator is \(1\) iff there exists any \(A_i\in\mathcal{A}\) such that \(A_i\subseteq P_k\).
5. Complete-set share is the mean complete-set indicator over tasks with an admissible reference.

The same selected reference is used for precision and recall. This avoids selecting a different alternative set for each side of the precision/recall point. An empty prediction set has precision=0, recall=0 and complete-set indicator=0; report coverage/abstention separately. Tasks with no admissible acceptable-set reference are excluded from these metrics, not scored as zero.

Bootstrap intervals use the evaluator's \`independent_unit_id\` (task or a declared cluster). A group with fewer than two independent units receives no CI and is listed in the export manifest.

## Baseline assignment reconciliation

The frozen E9 experiment object lists exactly: `rag_mcp`, `mcp_zero`, `per_subtask`, `colt_adapted`, `toolscope_adapted`, `cmtf_adapted` and `all_tools`.

The broader baseline catalogue marks `bm25` and `dense_lsa` as usable in E9, and the Core Protocol v2 baseline table mentions BM25/dense retrieval for E8/E9. They are **not** present in E9's frozen `baseline_ids` array. For this confirmatory E9 exporter, the experiment-specific assignment is authoritative: BM25 and Dense LSA are rejected as unregistered E9 primary methods until an explicit, versioned protocol amendment updates E9's baseline assignment and plotting plan. Do not add them to a run manifest as if they were preregistered.

## Protocol comparator reconciliation — unresolved before confirmatory execution

The original \`Experimental_Protocol_PaMCP.docx\` lists E9 comparators as COLT (retrained on MCP dev), MCP-Zero, ToolScope, CMTF with common contracts, and PaMCP without/with backward closure. The repository's machine-readable \`pamcp_experiments_v1.json\` instead assigns \`rag_mcp\`, \`mcp_zero\`, \`per_subtask\`, \`colt_adapted\`, \`toolscope_adapted\`, \`cmtf_adapted\`, and \`all_tools\`, with \`Full_PaMCP\` separately declared as primary.

These lists are not semantically identical:

- \`per_subtask\` performs independent per-subgoal retrieval and union; it is **not** a PaMCP ablation that changes only backward closure.
- \`rag_mcp\` should be retained as a clearly labelled simple retrieval control because it appears in the current manuscript, but it is not one of the five retained external baselines in the DOCX.
- \`all_tools\` is an exposure/control condition, not an external baseline.
- The current \`mcp_zero\` implementation is single-pass and does not reproduce the full iterative active-request protocol.
- The current \`colt_adapted\` implementation requires genuine training query/tool scenes; server co-membership is not a substitute.
- The current \`toolscope_adapted\` is a clean-room clustering adaptation, not the full merger + equivalence-check + correction + contextual reranking pipeline.
- CMTF consumes typed contracts; its errors are dependent on E2 contract quality.
- A true PaMCP-NoBackwardClosure configuration must preserve eligibility, cost-based set cover and the set-level checks while setting only the closure depth to zero. Do not alias \`per_subtask\` to this condition.

The exporter deliberately validates the repository's current frozen method IDs for software consistency. That does **not** resolve this research-protocol mismatch. Before confirmatory E9, version and approve a single comparator map, then update the frozen experiment/baseline catalogs and manuscript consistently. Until then, report method adapters as software-ready/blocked with fidelity labels; do not call them faithful reproductions or claim E9 completed.

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

## Executable E9 runner and accepted inputs

The campaign runner is **experiments/e9_retrieval_campaign.py**. It does not load evaluator/task_references.jsonl until the top-20 discovery rankings have been written and hashed. It refuses to start unless the E1, E2, E3 and E12 prerequisite artifacts are explicitly accepted and SHA-256 verified, and the comparator-map approval is in place.

Required input package:

| Input | Acceptance contract |
|---|---|
| Release gate | schema_version=1.0.0, status=accepted; E1/E2/E3/E12 each include status=accepted, artifact_path, SHA-256 and acceptance_id |
| Comparator map | status=accepted; exact baseline IDs from the frozen E9 experiment, separate Full_PaMCP primary ID, protocol DOCX SHA-256 and approval record |
| GoalSpecs | 94 tasks × 3 decomposition conditions = 282 frozen JSONL records; prompt hash, explicit no-evaluator-access flag and transformation provenance |
| Contract bundle | status=accepted; all 525 candidate tools hash-bound to their definition; no evaluator labels used; accepted E2 and E3 source-artifact hashes |
| Model profile | accepted E12 bundle with model ID/revision and measured ModelProfile class curves |
| Policy bundle | accepted and versioned E9 policy artifact |
| Composer config | accepted E9 ComposerConfig with K=20 and frozen refinement depth |
| Encoder bundle | accepted local SentenceTransformers snapshot, model ID/revision, package version and per-file SHA-256 list |
| COLT scenes | training-only JSONL; task IDs must not overlap the 94 E9 evaluation tasks |
| ToolScope oracle | independent, accepted positive/negative tool-equivalence pairs; not derived from E9 reference labels |

The runner uses a local-only SentenceTransformers model snapshot; it sets offline flags and does not silently download or substitute an encoder. It does not synthesize GoalSpecs, contracts, effects, model profiles, training scenes or equivalence labels. Method/adapter fidelity is preserved in the run manifest.

Launch command (after all input artifacts have been accepted):

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
      --training-scenes artifacts/e9/colt_training_scenes.jsonl \
      --equivalence-oracle artifacts/e9/tool_equivalence_oracle.json \
      --output-dir results/definitive/E9/e9-livemcpbench-run-001 \
      --run-id e9-livemcpbench-run-001 \
      --device cuda

The training-scenes and equivalence-oracle arguments may be omitted only when COLT and ToolScope are explicitly recorded as blocked; the resulting run is partial, not complete. MCP-Zero is recorded as the repository's single-pass adaptation, not as a faithful reproduction of the official active-request loop.

For every task × method × decomposition condition, the runner emits one ordered top-20 ranking. The exporter derives k=5,10,20 from that frozen ranking. It does not treat the three cutoffs as independent task observations. Full PaMCP is run once per task/decomposition with its frozen K=20 composition budget and certificate; its selected toolkit is recorded as the method output. A PaMCP abstention is retained as an empty prediction, not deleted from the denominator.

The runner output is results/definitive/E9/<run-id>/MANIFEST.json, discovery/rankings.jsonl and the copied evaluator references. The manifest remains partial whenever a registered method is blocked or incomplete.

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

The repository contains the pinned LiveMCPBench snapshot, a protocol-aligned 94-task preparer, an E9 retrieval campaign runner and an evaluator-separated metric exporter. The runner has not yet produced a definitive run: no accepted E1/E2/E3/E12 release gate, comparator approval, frozen 282-row GoalSpec matrix, accepted 525-tool contract bundle, E12 profile, policy/config/encoder package, COLT training scenes or ToolScope equivalence oracle has been supplied. Therefore E9 method comparisons and performance results are not yet available.
