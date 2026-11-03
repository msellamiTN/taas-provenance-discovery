# TaaS Studio information architecture

## Primary workspaces

| Workspace | Purpose | Capability boundary |
|---|---|---|
| Overview | API/host readiness and hardware diagnostics | Does not report model load state |
| Model Studio | Load selected HF model and run inference | Process-local; no multi-tenant scheduler |
| Agent Studio | Decompose objective into GoalSpec proposal | Structural validation only; no semantic proof or tool execution |
| Tools & MCP | Inspect configured MCP servers and tool schemas | initialize + tools/list only; no tools/call |
| Goal Design | Author and validate canonical GoalSpec | Human review remains required |
| Discovery | Find candidate toolsets | Discovery is not execution |
| Assurance | Review pre-execution certificates and counterexamples | Does not certify runtime behavior |
| Runs & Traces | Future governed invocation observability | Unavailable until invocation exists |

## User journeys

### Model inference
Select model → choose device → load → inspect process-local runtime state → submit prompt → inspect response and measured inference metadata.

### Agent proposal
Enter objective/context → generate with loaded model → inspect raw response and parse result → run full structural validation → review goal semantics, dependencies and effects → apply proposal to Goal Design → validate again before discovery.

### MCP discovery
Inspect configured server → view tool schema/annotations → select metadata → import into discovery request → review GoalSpec and policy → run discovery. No tool is called.

## State domains
- Host diagnostics: process, CPU/RAM/disk, CUDA/GPU detection and Colab detection.
- Model runtime: loaded model ID, device/dtype, load time, inference-executed state and last error.
- Agent proposal: raw text, parse status, structural validation, semantic review and applied status.
- MCP inspection: server identity, protocol metadata and tools list; never execution status.
- Discovery: request fingerprint, result and stale/invalidated state.
- Assurance: certificate and evidence freshness.
- Execution: not implemented in this milestone; no run/trace state is fabricated.

A transition in one domain must not imply another: GPU detected ≠ model loaded; model loaded ≠ inference executed; JSON parsed ≠ structurally valid; structurally valid ≠ semantically correct; selected tool ≠ task fulfilled; assurance certificate ≠ successful execution.
