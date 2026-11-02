# MCP-Bench integration — repository-retained mode

TaaS uses the benchmark assets retained inside this repository as its source of truth.
The Studio benchmark browser reads local repository data through `taas.data.registries`;
it does not clone, fetch, or depend on a live MCP-Bench upstream checkout.

## Retained assets

- `data/raw/livemcpbench/tools.json`
- `data/raw/livemcpbench/all_annotations.json`
- `data/raw/SOURCES.txt`
- `data/calibration/`
- `data/processed/`
- `data/llm_records/`

The repository's processed registries are loaded by the TaaS data layer. Benchmark task
browsing intentionally omits gold tool labels. Gold labels belong only in the evaluation
stage after discovery has completed; they must not be sent to the analyst or discovery
request.

## Studio workflow

1. Open the authenticated Studio benchmark workspace.
2. Browse the retained dataset and select a task prompt.
3. Review the prompt and author or validate a structured GoalSpec.
4. Search the retained tool registry and select candidate tools.
5. Run discovery and inspect the selected toolkit, capability gaps, abstention reasons,
   trust decisions, and certificate checks.
6. Evaluate the discovery result against benchmark gold labels in the separate evaluator.

## Runner integration boundary

`src/taas/mcpbench.py` contains the repository-side adapter and result semantics.
`integrations/mcp-bench/runner.patch` is retained as a historical integration artifact
for source review only. It is not applied automatically and is not part of the Studio
workflow.

Do not clone or fetch a live upstream repository as part of this project workflow.
Do not run `git apply --check` or apply the historical patch against any checkout.
Any future runner integration must be implemented and validated against code and data
retained in this repository, with explicit tests and an auditable local fixture.

## Evaluation semantics

- Completed, failed, and abstained tasks remain distinct.
- Abstentions are not counted as execution failures or successful completions.
- Judge and accuracy metrics are unavailable (`null`) when no task was evaluated.
- Multi-file task counts are summed; aggregate rates are recomputed from summed counts.

No live MCP server execution or benchmark run is implied by the retained integration code.
