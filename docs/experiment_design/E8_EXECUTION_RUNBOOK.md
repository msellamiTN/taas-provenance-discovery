# E8 — Single-tool retrieval quality: execution runbook

## Decision and scope

E8 evaluates single-tool candidate retrieval. It does not evaluate multi-tool composition, observed side effects, access-control enforcement, prompt-injection resistance, or task execution.

The run keeps benchmark tracks separate. Scores must never be pooled across ToolRet and MCPToolBench++ because their corpus identities, query distributions and annotation semantics differ.

## Dataset tracks and inclusion rules

| Track | E8 role | Inclusion rule | Label semantics / boundary |
|---|---|---|---|
| ToolRet | Primary heterogeneous retrieval track | Full pinned tool corpus; every non-empty query with original qrels | Graded relevance judgments. Not an MCP execution or security benchmark. |
| MCPToolBench++ | MCP-specific single-target retrieval track | Current repository subset: 87 tools / 10 servers; retain only tasks with exactly one resolved primary function-call target | Primary function_call_label is the strict target. Multi-target, unresolved and ambiguous tasks are excluded and counted. |
| MCPToolBench++ similar_tools | Sensitivity analysis only | Resolve source-annotated alternatives against the same 87-tool candidate corpus | Add primary target plus resolved similar_tools; never replace the strict primary score with this permissive score. These labels are alternatives recorded by the source, not independently validated exhaustive relevance sets. |
| MCP-Atlas public | Candidate-retrieval diagnostics | Public 500-task release; preserve per-task ENABLED_TOOLS visibility | TRAJECTORY is a successful diagnostic trace, not exhaustive acceptable-tool-set gold. This runner leaves the track blocked until a frozen identity-resolution and coverage-only diagnostic is added. |
| B1 / B1m | Intended single-tool tracks in the E8 catalogue | No source data or split is currently present in the repository tree | BLOCKED_DATA; do not silently replace with another source. |
| MCPVerse v1.1 | E9 multi-tool discovery track | Use pinned time-invariant v1.1 CSV and native evaluation semantics | Does not provide a full candidate registry; not used as an E8 standalone corpus. |

ToolRet uses the independent immutable revisions already recorded by the prior benchmark artifact:
- query repository: mangopy/ToolRet-Queries, revision b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445
- tool repository: mangopy/ToolRet-Tools, revision e06c38c75612b6536bd959e08cdd345894aba6a7

MCPToolBench++ raw data are acquired by scripts/fetch_data.sh, which pins:
- LiveMCPBench: 36a51a1065dda49c1e503b87edf33a1e0b331a74
- MCPToolBench++: 2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037

The E8 run records the exact source revisions, input hashes, counts and task exclusions. The MCPToolBench++ subset is not represented as the full upstream 4,000-server benchmark.

## Discovery/evaluator separation

Discovery receives only:
- query text and non-label task metadata;
- the complete candidate-tool corpus for that dataset track.

Evaluator-only references are loaded separately and are not passed to any ranking method. Before scoring, the runner writes all per-task ranking files. It then loads qrels and computes metrics.

For ToolRet, all qrels tool IDs must exist in the full tool corpus. The adapter rejects missing candidate documents and discovery records containing evaluator fields. It does not construct a candidate corpus from positive qrels.

For MCPToolBench++, the primary target is the sole resolved function_call_label. The separate similar-tool sensitivity qrels preserve the primary target and add only alternatives from similar_tools that resolve to tool definitions in the same source snapshot. The strict single-target score remains the primary result.

## Baseline suite

| Baseline ID | Method | Fidelity and limitations |
|---|---|---|
| random | Deterministic seeded random ranking | Sanity floor; seed is task-stable. |
| bm25 | BM25 over tool name, server, category, description and input schema | Lexical baseline. |
| tfidf | TF-IDF cosine ranking over the same tool text | Lexical baseline. |
| dense_lsa | TF-IDF plus truncated SVD (128 dimensions maximum) | Explicit surrogate; not a neural dense encoder and not E5/BGE. |
| e5_dense | intfloat/e5-small-v2, query/passage prefixes and cosine ranking | Neural dense retrieval; record immutable Hugging Face model revision. |
| bm25_e5_rrf | Reciprocal-rank fusion of BM25 top-100 and E5 top-100 | Explicit retrieval adaptation; fusion uses RRF_K0=60, no test-set tuning. |
| cross_encoder | cross-encoder/ms-marco-MiniLM-L-6-v2 reranks BM25 top-100 | Reranker adaptation. Always report the BM25 top-100 candidate recall ceiling. |

The model revision is resolved once from Hugging Face and passed to the runner as an immutable commit SHA. The exact model IDs, revisions and execution device are recorded in the run manifest.

The registered rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted and cmtf_adapted methods are not silently relabelled as these rankers:
- rag_mcp needs its own frozen adaptation and is not inferred from an E5 ranking.
- mcp_zero requires its active-request protocol; the current repository adapter is a single-pass adaptation.
- per_subtask requires frozen GoalSpecs; E8 does not infer decompositions from qrels.
- colt_adapted needs an explicit training split and training-only scenes.
- toolscope_adapted needs independent equivalence labels to evaluate merging.
- cmtf_adapted needs independently sourced typed contracts.
They remain explicit blocked / not-comparable entries in the run manifest.

## Metrics and inference

Primary metrics:
- Hit@1
- Hit@5
- MRR@10
- macro Hit@1 (unweighted mean of category-level Hit@1 values, with category and task denominators)

Secondary metrics:
- Precision@k, Recall@k, MRR@k, nDCG@k and Hit@k for k = 1, 5, 10
- per-task metric CSVs and category-stratified Hit@1
- Cross-encoder candidate recall@100, calculated before reranking

Paired comparisons are made against BM25:
- task-level paired bootstrap for ToolRet;
- target-server-cluster paired bootstrap and sign-flip tests for MCPToolBench++;
- exact sign-flip enumeration for at most 18 independent units and seeded Monte Carlo sign flips otherwise;
- Holm adjustment over the preregistered baseline/metric comparison family within each track.

For MCPToolBench++, the bootstrap confidence interval resamples whole target-server clusters. Its task-weighted point estimate and cluster-resampled interval are both explicitly recorded. Seeds are not counted as independent task observations.

Primary MCPToolBench++ metrics use only the single primary target. The annotated-similar-tools sensitivity file is clearly separate and must not replace the primary table.

## Resumption, immutability and outputs

Each run is written under a unique directory:
results/definitive/E8/<run-id>/

The runner:
- records source and model fingerprints in RUN_STATE.json;
- writes per-baseline ranking caches atomically;
- skips a cache only when its data/model/config fingerprint and task/candidate coverage match;
- rejects resumption when source hashes, model revisions, top_k, seed or runner commit differ;
- refuses to modify a finalized run containing MANIFEST.json;
- writes raw rankings, per-task metrics, aggregate metrics, paired tests, exclusions, PNG plots, source hashes and a ZIP bundle.

To resume an interrupted run, rerun with the same --run-id, the same input snapshots, the same model revisions, device, top_k and seed. A changed configuration requires a new run ID.

## Colab execution

Open notebooks/PaMCP_E8_Retrieval_Campaign.ipynb and run all cells. The notebook:
1. refreshes the exact PaMCP branch checkout;
2. installs test, benchmark and sentence-transformer dependencies;
3. fetches the pinned MCPToolBench++ raw sources;
4. runs the E8 unit tests;
5. acquires ToolRet at its pinned query/tool revisions;
6. resolves exact E5 and cross-encoder model revisions;
7. executes the E8 campaign and exports the ZIP artifact.

The notebook requires network access to GitHub and Hugging Face for dataset/model acquisition. It makes no paid LLM API calls. Use a Colab GPU runtime for practical dense encoding and cross-encoder throughput.

## Acceptance status

A successful runner invocation means the selected retrieval baselines have executed over the two available data tracks. It does not mean all of E8 is complete.

The runner marks the campaign partial because:
- B1/B1m data are absent;
- MCP-Atlas trajectory diagnostic mapping has not been frozen;
- the registered planning/adaptation baselines remain blocked by missing GoalSpecs, training splits or independent contract oracles.

Do not change E8's catalogue status to completed until the complete preregistered dataset/baseline matrix is executed or explicitly amended and accepted. E8 alone cannot support claims about PaMCP end-to-end superiority, safety, composition validity or runtime effects.
