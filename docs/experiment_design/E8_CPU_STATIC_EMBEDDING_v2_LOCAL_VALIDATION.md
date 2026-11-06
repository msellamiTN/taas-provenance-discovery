# Local validation — E8-CPU-StaticEmbedding-v2 (pretrained FastText)

Date: 2026-11-06

## Change
The former Skip-gram training path is removed. E8-v2 loads the official pretrained cc.en.300.bin Common Crawl model. No training or fine-tuning is performed.

## Storage behavior
- Default ephemeral download: stream-decompress official HTTPS gzip into a temporary file, hash it, atomically finalize, load once, then delete the on-disk binary.
- Configurable free-space preflight; default safety threshold 8 GiB.
- Optional local model path or persistent external cache.
- Model binary is never committed to Git.
- Ephemeral mode saves persistent storage only. Temporary disk and sufficient RAM are still required; the full model is multi-GB.

## Required checks
1. Unit tests for gzip download, atomic replacement, insufficient-disk failure, cleanup, 300d dimension validation and absence of training calls.
2. Actual model-load smoke test; record source, SHA-256, bytes, load time and peak RSS.
3. Verify subword/OOV lookup using an unseen token.
4. Run 100-query smoke test separately on ToolRet and MCPToolBench++ strict.
5. Verify unchanged metric keys and denominators: Hit@1, Hit@5, MRR@10, Macro Hit@1.
6. Full tracks only after smoke tests and resource review pass.

## Execution status
Not yet executed in this environment: actual model download/load, real model OOV test, dataset smoke tests and benchmark metrics. Prior fake-vector tests do not validate the pretrained model. No quality or superiority claim is made.