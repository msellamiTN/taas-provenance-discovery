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
   the native evaluator. It is not scored as ordinary task success or execution failure.
7. The TaaS trace is attached as `result["taas"]` for successful executions and as a
   top-level `taas` field for abstentions.
8. Aggregation reports `completed_tasks`, `failed_tasks`, and `abstained_tasks`
   separately; completion rate is completed / total.
9. When no task was evaluated, judge and accuracy metrics are `null` (unavailable),
   not numeric zero. Multi-file task counts are summed, not averaged.

## Validation boundary

The patch is based on source inspection of the pinned upstream runner and executor.
It has **not** been applied with `git apply --check` or executed against a local
upstream checkout in this environment. Network access to clone the upstream
repository was unavailable during authoring. Treat successful application and
runner-level smoke tests as mandatory gates before benchmark runs.

The patch does not claim that a live MCP server has been executed.

## Abstention accounting semantics

For a run with `C` completed, `F` failed, and `A` abstained tasks:

- `total_tasks = C + F + A`
- `completion_rate = C / total_tasks` (zero when there are no tasks)
- `failed_tasks = F`; abstentions are never folded into failures
- `abstained_tasks = A`
- Judge metrics are `null` when `C = 0`, because no judge observations exist
- Across task files, task counts are summed and the completion rate is recomputed
  from the summed counts (not averaged from per-file rates)

Legacy result files without `abstained_tasks` are treated as having zero abstentions.
