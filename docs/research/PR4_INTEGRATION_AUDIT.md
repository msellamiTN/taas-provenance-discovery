# PR #4 integration audit — TaaS / MCP-Bench

**Audited revision:** `58f83c00c7f6e14c846a6174ced482a02d9de98f`  
**Pull request:** [#4 — Integrate TaaS discovery into MCP-Bench](https://github.com/msellamiTN/taas-provenance-discovery/pull/4)  
**Audit date:** 2026-11-02  
**Scope:** static source inspection and GitHub Actions status; no live MCP-Bench execution performed.

## 1. Verified status

- PR #4 is open and marked draft.
- Base branch: `feature/benchmark-capability-hypergraph`.
- Head branch: `feature/taas-mcpbench-integration`.
- Head SHA: `58f83c00c7f6e14c846a6174ced482a02d9de98f`.
- Changed files: MCP-Bench adapter, analyst, integration documentation, two test files and workflow configuration.
- GitHub Actions run `41355356757`, workflow “Benchmark hypergraph validation”, completed successfully.
- Its `unit-tests` job completed successfully, including the full regression suite and benchmark hypergraph build.

A passing CI run verifies the tests executed by that workflow. It does **not** establish live runner integration, protocol fidelity under execution, benchmark task success or research results.

## 2. Verified implementation

### 2.1 Tool catalogue adapter

`raw_tools_from_mcpbench`:
- Converts the supplied mapping into existing `RawTool` objects.
- Maps tool identity to `server::tool`.
- Retains the original MCP-Bench key for mapping selected tools back.
- Supports `input_schema` / `inputSchema` and `output_schema` / `outputSchema`.
- Rejects duplicate TaaS identities.

The inspected `RawTool` dataclass supports the fields passed by the adapter, including `extra`.

### 2.2 Discovery adapter

`TaaSMCPBenchAdapter.select`:
- Calls an injected GoalSpec factory.
- Extracts contracts.
- Instantiates `DiscoveryEngine`.
- Calls `discover`.
- Maps the selected toolkit back to the MCP-Bench tool-map keys.
- Returns a sidecar trace containing discovery and analyst timing, GoalSpec, selection, abstention, gap, certificate, counterexample and composition statistics.

The inspected `DiscoveryEngine.discover` accepts either a parsed GoalSpec or a dictionary and returns the fields referenced by the adapter.

### 2.3 Analyst

`MCPBenchGoalAnalyst`:
- Uses an injected MCP-Bench LLM provider.
- Supplies only task text in its user prompt.
- Parses JSON and validates several structural properties.
- Captures raw response, usage and prompt version.

The prompt explicitly prohibits tool selection and use of gold mappings. This is a good separation boundary, but it must also be enforced by the runner and data plumbing.

## 3. Gaps and risks before benchmark claims

### G1 — No native runner hook yet (blocking)

The PR documentation explicitly says the adapter is not yet wired into the pinned MCP-Bench runner. The next implementation must inspect the exact pinned checkout and add a minimal pre-execution hook after server discovery and before the native agent receives its tool map.

**Required evidence:** baseline and TaaS each execute at least one identical task through the same native executor and evaluator.

### G2 — No live end-to-end MCP smoke test (blocking)

Current adapter tests cover catalogue conversion and identity handling. Analyst tests cover the analyst interface. They do not establish that a real MCP server, MCP-Bench server manager, task executor and evaluator work together with TaaS.

**Required evidence:** a safe, deterministic one-task smoke test with a captured native result and TaaS sidecar trace.

### G3 — GoalSpec validation should be strengthened

The analyst validates required keys, unique IDs, dependency references and sigma values. Further checks should be added for:
- dependency cycles;
- supported goal classes and type syntax;
- required field types and non-empty identifiers;
- optional/default fields and numeric bounds;
- consistency of prompt inputs, dependencies and output requirements.

Malformed or cyclic GoalSpecs should fail closed before discovery.

### G4 — Provenance evidence semantics require explicit benchmark policy

MCP-Bench tool metadata may contain schemas, descriptions and MCP annotations, but this does not mean that runtime-observed or cryptographically attested evidence exists. Contract extraction may therefore rely on lexical and annotation evidence.

Before choosing a benchmark trust threshold, inspect how the composer applies evidence thresholds and measure the eligible-tool count. Do not silently upgrade metadata-derived evidence to runtime observation or attestation.

**Required evidence:** a report of evidence types and eligibility outcomes on the exact benchmark catalogue, plus a documented benchmark policy rationale.

### G5 — Abstention behavior needs runner-level verification

The adapter returns an empty tool map on abstention. Verify the native executor's behavior with an empty tool map: it may answer directly, fail, or handle the case differently. Record this as an explicit TaaS abstention outcome rather than treating it as a normal execution failure.

### G6 — GoalSpec analyst overhead and model settings

The adapter records analyst timing and usage, but the experiment manifest must also bind:
- exact model/provider identifier;
- prompt hash and version;
- temperature and token limits;
- response parsing version;
- retries and timeout;
- whether the native benchmark agent shares the same provider/model deployment.

Include analyst cost and latency in total TaaS system cost and latency, while also reporting them separately.

### G7 — Trace privacy and reproducibility

The adapter currently captures the analyst raw response. Before persistent trace storage, apply redaction and retention rules. Preserve exact non-secret experiment settings, task hashes, tool-map snapshot hashes, TaaS commit and certificate references. Never persist API credentials or sensitive task/tool data unnecessarily.

### G8 — Benchmark separation

The repository contains data loaders and registry code for LiveMCPTool / LiveMCPBench and MCPToolBench++. Those datasets are not interchangeable with the MCP-Bench protocol. Build separate adapters and evaluators; do not reuse MCP-Bench assumptions for those benchmarks without inspecting their native runner contracts.

## 4. Colab T4 implications

The current TaaS discovery core is CPU-oriented: its declared dependencies include NumPy, SciPy, scikit-learn and Matplotlib. The inspected engine performs hypergraph construction, bitmap indexing, retrieval and composition without requiring CUDA.

Therefore:
- Colab CPU is sufficient for a first functional Studio prototype.
- Colab T4 is useful only for optional GPU-backed embedding, reranking or local inference extensions.
- A T4 runtime must not be presented as accelerating the current core unless a CUDA-backed component is actually executed and measured.
- Studio state, manifests, traces and artifacts must persist outside the ephemeral Colab runtime.
- Colab is a demo/research worker, not the production control plane or durable database.

See `docs/deployment/COLAB_T4_CORE_STUDIO.md` for the deployment profile and acceptance gates.

## 5. Recommended next implementation order

1. Inspect and pin the exact MCP-Bench runner API at the documented commit.
2. Add a thin runner hook that filters only the agent-visible tool catalogue.
3. Verify native empty-tool/abstention behavior.
4. Add one deterministic live MCP server smoke test.
5. Measure provenance eligibility and validate benchmark policy settings.
6. Strengthen GoalSpec validation and sidecar redaction.
7. Run paired baseline/TaaS tasks through the unchanged native evaluator.
8. Expose the same core through a minimal FastAPI service.
9. Build the Studio UI and Colab launcher on top of the service.

## 6. Audit conclusion

PR #4 is a useful and CI-validated adapter foundation. It is **not yet a completed MCP-Bench integration** and does not yet support empirical claims. The next research-critical milestone is the native runner hook plus a real one-task smoke test. In parallel, the Colab T4 target should be implemented as an ephemeral deployment profile with external persistence and optional, explicitly measured GPU extensions.
