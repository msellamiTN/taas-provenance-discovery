# Local validation — E8-CPU-StaticEmbedding-v2

Date: 2026-11-06

## Environment
- Python 3.13.5, Linux x86_64.
- NumPy and pytest available.
- `fasttext-wheel==0.9.2`: not installed.
- Installation attempt blocked because this execution environment has no DNS/network access.
- Pinned benchmark snapshots are not mounted in this execution environment.

## Executed checks
- Tokenization and IDF.
- Weighted pooling and normalized vectors.
- OOV/subword lookup interface.
- Explicit zero-query abstention.
- Exact cosine ranking and deterministic tie-breaking.
- Checkpoint resume and fingerprint mismatch rejection.
- Fail-closed behavior when FastText dependency is missing.
- **Unit tests: PASS (9/9).**
- **Python compilation: PASS.**
- **Experiment JSON parsing: PASS.**

The unit tests use a deterministic fake FastText vector provider. They validate mechanics, not the quality of a trained FastText representation.

## Not run / blocked
- Actual FastText Skip-gram training: BLOCKED (dependency unavailable).
- ToolRet and MCPToolBench++ dataset-level smoke tests: NOT RUN (snapshots unavailable).
- Target Colab CPU/GPU attestation: NOT RUN.
- Full benchmark metrics and statistical comparisons: NOT RUN.

No retrieval-quality result or superiority claim is made.
