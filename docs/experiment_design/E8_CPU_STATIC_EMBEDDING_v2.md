# E8-CPU-StaticEmbedding-v2

**Status:** implementation candidate; unit-tested locally. Full model training and benchmark execution remain pending the pinned FastText dependency and dataset snapshots.

## Scope and compatibility

This is a new, isolated retrieval-method variant for the definitive E8 single-tool retrieval experiment. It does not replace or mutate the original E8 runner, E5/cross-encoder configuration, checkpoints, or results.

It reuses the original E8 loaders and evaluator:
- ToolRet heterogeneous retrieval track, retaining graded qrels.
- MCPToolBench++ strict single-primary-target track.
- MCPToolBench++ similar-tools labels remain a separately reported sensitivity analysis.
- Tracks are evaluated independently; metrics are never pooled.
- Primary E8 metrics remain Hit@1, Hit@5, MRR@10 and macro Hit@1.

## Method

1. Construct tool documents from discovery-side tool name, description and schema fields.
2. Apply the original E8 tokenizer: case-folded `[a-z0-9_]+`.
3. Train official FastText Skip-gram on tool documents only. Queries and evaluator qrels are excluded from training.
4. Reference parameters: 300 dimensions, window 5, character n-grams 3–6, 5 negative samples, 10 epochs, minCount 1, one CPU thread, negative-sampling loss.
5. Compute smoothed IDF over tool documents only:
   `idf(t) = ln((N+1)/(df(t)+1)) + 1`.
6. Encode each query/tool as an L2-normalized IDF-weighted mean of FastText word/subword vectors.
7. Rank the complete candidate universe by exact cosine similarity. Ties are resolved by the existing E8 stable tool-ID tie-break.
8. Empty or zero query vectors abstain with an empty ranking; they are counted, not assigned arbitrary results.

FastText is a static subword-aware embedding, not a contextual Transformer or a generative LLM.

## CPU and reproducibility controls

- CPU-only implementation; the runner sets `CUDA_VISIBLE_DEVICES=""`.
- One FastText training thread.
- Record Python/platform, CPU count, FastText package version, configuration, dataset manifests, model SHA-256 and output artifacts.
- The FastText Python training API has no documented user seed parameter. The E8 seed may govern task order/sampling only; it is not claimed to make FastText training deterministic. Preserve the exact trained model artifact.
- Atomic, fingerprinted ranking checkpoints every 16 tasks.
- Checkpoint fingerprints include track, task IDs and text, candidate IDs and text, model hash and complete configuration.
- Never reuse checkpoints across changed fingerprints.
- Model binaries, benchmark data and result bundles are run artifacts and must not be committed.

## Baselines

This adds FastText as a separately identified method. It does not silently replace BM25, TF-IDF, LSA, E5, RRF, cross-encoder or other assigned E8 baselines. Every comparison must use the same track, candidate universe, query set and relevance judgments.

## Validation gates

- G0: original E8 adapters verify dataset snapshots and exact denominators.
- G1: discovery/evaluator separation; no labels/qrels enter model training.
- G2: model dimensions, finite vectors and non-empty tool representations.
- G3: exact cosine ranking, deterministic ties and explicit abstention.
- G4: CPU-only execution attested in target runtime.
- G5: original E8 metric implementation used without changing denominators.
- G6: checkpoint atomicity, fingerprint rejection and resume verified.
- G7: model, data and result hashes recorded.

## Current execution status

Local unit tests use a deterministic fake vector provider. They validate pooling, ranking, abstention and checkpoint mechanics, not learned FastText quality. Actual Skip-gram training requires `fasttext-wheel==0.9.2`; dataset-level smoke tests require the pinned ToolRet and MCPToolBench++ snapshots. No benchmark score or superiority claim is made.
