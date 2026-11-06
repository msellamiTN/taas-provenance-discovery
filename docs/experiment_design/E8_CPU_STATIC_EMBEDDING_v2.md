# E8-CPU-StaticEmbedding-v2 — pretrained FastText (Common Crawl)

**Status:** implementation candidate. No model training or fine-tuning is performed.

## Frozen scope and metrics
- ToolRet heterogeneous retrieval and MCPToolBench++ strict single-primary-target remain separate tracks.
- Similar-tools labels remain a separately reported sensitivity analysis.
- Primary metrics remain Hit@1, Hit@5, MRR@10 and Macro Hit@1; no pooled denominators.
- This isolated variant does not modify the original E8 runner, E5/cross-encoder configuration, checkpoints or results.

## Pretrained model
- Artifact: `cc.en.300.bin` from the official fastText Common Crawl + Wikipedia release.
- Source: https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.en.300.bin.gz
- 300 dimensions, character n-gram/subword inference and OOV support.
- The published model was trained with CBOW + position weights. E8 only loads it for inference; no local training, epochs, training seed or fine-tuning.
- Official docs: https://fasttext.cc/docs/en/crawl-vectors

## Storage-aware lifecycle
Default is ephemeral: check free disk (8 GiB safety threshold), stream-decompress HTTPS gzip directly to a temporary binary (no separate .gz file), hash it, atomically finalize, load once for both tracks, then delete the disk file. An optional external cache retains a reusable copy; `--model-path` accepts an existing binary.

Ephemeral mode reduces persistent storage but still requires several GiB of temporary disk and adequate RAM. The model is multi-GB, not a small-footprint artifact. If resources are insufficient, stop rather than silently switching to text vectors, which do not preserve full binary FastText OOV/subword inference. Never commit the model to Git or benchmark output.

## Retrieval method
1. Build discovery-side tool documents from tool name, description and schema fields.
2. Apply the frozen E8 case-folded `[a-z0-9_]+` tokenizer.
3. Obtain token vectors from the pretrained binary, including subword composition for OOV tokens.
4. Compute smoothed IDF per track over candidate tool documents only: `idf(t)=ln((N+1)/(df(t)+1))+1`.
5. Encode query/tool text using IDF-weighted mean pooling and L2 normalization.
6. Rank the complete candidate universe by exact cosine; preserve stable tool-ID tie-break.
7. Empty/zero query vectors abstain and are counted explicitly.

## Validation gates
- G0 dataset snapshot and denominator verification with original E8 adapters.
- G1 no labels/qrels in representation construction or IDF.
- G2 verify model source, 300d dimension, finite vectors, subword OOV behavior and SHA-256.
- G3 disk preflight, streamed gzip decompression, atomic download, cleanup and fail-closed behavior.
- G4 CPU-only attestation; record model-load time and peak RSS.
- G5 exact cosine ranking, stable ties and zero-query abstention.
- G6 unchanged primary metric implementation and separate track reporting.
- G7 checkpoint atomicity, fingerprint rejection and resume.
- G8 100-query smoke test per track before full execution.

No benchmark score or superiority claim is made until the real model and pinned dataset snapshots are executed.