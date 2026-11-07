# PaMCP E1 Colab Runner v1.3 — No-upload edition

This notebook is designed to be opened directly in Google Colab and run from top to bottom.

## What is included
- The approved 22-case unresolved E1 intake is embedded in the notebook.
- No CSV upload and no Google Drive mount are required.
- Runtime preflight and provenance coverage checks.
- Explicit manifest validation and execution approval gate.
- Evidence bundle generation.

## Scientific and safety boundaries
- The 22 intake cases do not have verified source-server identities in this package. The notebook must not infer identities from tool names or prefixes.
- Real MCP execution remains blocked for a case until its exact benchmark source, repository, pinned commit, artifact digest, tool name, schema digest, and credential-free status are verified.
- Colab is an ephemeral hosted runtime, not a security sandbox. Do not provide secrets or execute untrusted server code.
- A successful MCP protocol response is not evidence of a side effect. Independent observation is required.
- No E1 label or scientific result is changed or claimed by this notebook.

## Open in Colab
Open the notebook file in GitHub, then choose **Open in Colab** (or use Colab's File → Open notebook → GitHub flow).

