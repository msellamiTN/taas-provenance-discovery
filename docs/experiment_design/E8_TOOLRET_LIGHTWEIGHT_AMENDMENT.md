# E8 ToolRet Lightweight Retrieval Amendment

**Amendment ID:** `E8-TOOLRET-LIGHTWEIGHT-RRF-v1`  
**Applies to:** ToolRet heterogeneous retrieval track only  
**MCPToolBench++:** unchanged  
**Status:** implementation amendment; results must be reported separately from any run produced by the prior runner

## Motivation

The previous CPU campaign incurred substantial runtime from Cross-Encoder reranking over the ToolRet BM25 top-100 candidate pool. ToolRet contains 7,960 queries and 44,453 candidate tools. The Cross-Encoder is not required to preserve a useful lexical retrieval comparison.

## Exact method change

For ToolRet:

- Retain Random, BM25, TF-IDF, Dense LSA, E5 dense, and BM25+E5 RRF controls.
- Do **not** execute Cross-Encoder inference.
- Add `bm25_tfidf_rrf`, a deterministic lexical hybrid that fuses BM25 and TF-IDF top-100 candidate rankings with Reciprocal Rank Fusion:

\[
\operatorname{RRF}(d)=\frac{1}{60+r_{\mathrm{BM25}}(d)}
+\frac{1}{60+r_{\mathrm{TFIDF}}(d)}.
\]

- Return the top-10 fused candidates (or the configured `top_k`).
- Use deterministic tie-breaking by tool ID.
- Cache the TF-IDF top-100 candidate rankings and fused rankings independently.

For MCPToolBench++:

- Preserve the original baseline set, including E5 dense, BM25+E5 RRF, and Cross-Encoder reranking over BM25 top-100.
- Preserve its original strict single-primary-target subset and evaluation semantics.

## Scientific interpretation

BM25+TF-IDF RRF is a **lexical hybrid**, not a semantic or neural reranker and not an equivalent replacement for Cross-Encoder. It tests whether combining two sparse lexical ranking signals improves retrieval under the same candidate corpus. Results must not be described as semantic reranking or as evidence of Cross-Encoder parity.

The tracks remain separate. No cross-track pooling is permitted.

## Run isolation and reproducibility

- The prior run directory, partial checkpoints, and artifacts are immutable and must be preserved.
- The changed runner has a different code fingerprint. Start a **new run ID**; do not resume the previous Cross-Encoder ToolRet run.
- The notebook adds an amendment identifier to its run configuration fingerprint so its active-run recovery logic will not select the prior run.
- Record the new run ID, runner commit, dataset revisions, model revisions, CPU configuration, and manifest in the result report.

## Baseline matrix

| Track | Baselines |
|---|---|
| ToolRet | Random, BM25, TF-IDF, Dense LSA, E5 dense, BM25+E5 RRF, BM25+TF-IDF RRF |
| MCPToolBench++ | Random, BM25, TF-IDF, Dense LSA, E5 dense, BM25+E5 RRF, Cross-Encoder |

## Acceptance checks

1. Unit tests verify deterministic RRF ordering and task-coverage validation.
2. The end-to-end fixture verifies that ToolRet has `bm25_tfidf_rrf` and does not have `cross_encoder`.
3. The same fixture verifies that Cross-Encoder is still called for MCPToolBench++.
4. The final manifest reports per-track baseline suites and explicitly marks ToolRet Cross-Encoder as `NOT_RUN_BY_DESIGN`.
5. Full benchmark execution is a separate step. Passing software tests is not benchmark evidence.

## Scope limitations

This amendment does not change the frozen E8 dataset snapshots, task filtering, qrels, metrics, statistical tests, seeds, top-k, or the preregistered protocol baseline identities. It changes only the selected retrieval-control implementation for the ToolRet track and adds a lexical hybrid control. E8 remains partial until its original completion gates and unavailable data/baseline blockers are addressed.
