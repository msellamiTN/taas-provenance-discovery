# TaaS Multi-Agent Experiment Lab (Codex)

This directory defines the controlled orchestration protocol for extending and independently reproducing the TaaS experiments with Codex. It is additive: the existing implementation, datasets, LLM records, result JSON, plots, reports, and paper assets remain the historical baseline.

## Non-negotiable preservation rules

1. Never delete, rename, rewrite, or regenerate historical files under `results/`, `data/`, `docs/RESULTS.md`, or existing experiment outputs as part of a new run.
2. Do not run `reproduce.sh` or `experiments/run_all.py` as a first action. First inspect their side effects and establish a baseline snapshot.
3. Every new execution writes to a unique `results/runs/<run_id>/` directory. A run ID is immutable once populated.
4. A result is not "verified" merely because Codex reports success. Preserve raw stdout/stderr, exit status, environment, commit, config, input hashes, and output hashes.
5. Existing repository-reported numbers are historical claims until independently reproduced. Never silently merge historical and newly executed measurements.
6. No network calls, live MCP server execution, external API billing, destructive actions, or access to real user data without explicit approval and a documented sandbox.
7. Agents may inspect freely; code changes are isolated to agent worktrees/branches. Only the coordinator integrates reviewed patches.
8. If an experiment cannot be executed safely or faithfully, record BLOCKED with the reason. Do not substitute synthetic results without labeling them synthetic.

## Entry points

- [Protocol](PROTOCOL.md): phases, gates, evidence model, review workflow.
- [Agent contracts](AGENTS.md): role boundaries and deliverables.
- [Experiment matrix](experiment-matrix.yaml): E0–E13 scope, status, dependencies and acceptance evidence.
- [Coordinator prompt](prompts/COORDINATOR.md): paste into Codex at repository root.
- [Run validator](../scripts/validate_run_bundle.py): validates a run bundle's evidence manifest and file hashes.

## Run state vocabulary

`PLANNED`, `INSPECTED`, `READY`, `RUNNING`, `BLOCKED`, `FAILED`, `COMPLETED_UNVERIFIED`, `VERIFIED`, `REJECTED`.

Only the independent reproducibility reviewer can promote a run to `VERIFIED`. Completion and verification are different states.
