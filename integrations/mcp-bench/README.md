# MCP-Bench runner integration patch

This directory contains the runner-side integration patch for the pinned upstream
MCP-Bench revision.

- Upstream: https://github.com/Accenture/mcp-bench
- Required revision: `7a8eaeae83a842a2949080acc5473f65e1569daf`
- Target file: `benchmark/runner.py`
- TaaS adapter: `src/taas/mcpbench.py`

## Apply

From a checkout of the exact upstream revision, with this repository available on disk:

```bash
git checkout 7a8eaeae83a842a2949080acc5473f65e1569daf
git apply --check /path/to/taas-provenance-discovery/integrations/mcp-bench/runner.patch
git apply /path/to/taas-provenance-discovery/integrations/mcp-bench/runner.patch
```

The patch is intentionally opt-in. The experiment harness injects the configured
adapter with `runner.taas_adapter = adapter`. If that attribute is absent, native
MCP-Bench behavior is unchanged.

## Behavior

1. TaaS discovery runs after MCP server connection and tool discovery.
2. A non-empty selected subset is used to construct the native `TaskExecutor`.
3. The live server manager is restored before execution, preserving native dispatch.
4. The executor retains its selected tool snapshot.
5. The native evaluator still receives the complete catalogue in
   `result["available_tools"]`.
6. A TaaS abstention returns `status="abstained"` before agent execution and before
   the native evaluator. It is not scored as ordinary task success.
7. The TaaS trace is attached as `result["taas"]` for successful executions and as a
   top-level `taas` field for abstentions.

## Validation boundary

The patch was regenerated with `git diff` from the pinned upstream checkout
(`7a8eaeae83a842a2949080acc5473f65e1569daf`) and verified there with
`git apply --check`; the patched `benchmark/runner.py` compiles (`python -m py_compile`).
The earlier hand-written version had one line of leading and no trailing context per hunk,
which `git apply` rejects (it treats such hunks as anchored to the end of the file);
`tests/test_runner_patch_format.py` now checks hunk consistency offline. The runner has not
been executed, and runner-level smoke tests remain a mandatory gate before benchmark runs.

The patch does not claim that a live MCP server has been executed.
