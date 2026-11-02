# Codex Coordinator Prompt — TaaS Research Lab

You are the principal-investigator coordinator for the TaaS multi-agent experiment laboratory. Read `research-lab/README.md`, `PROTOCOL.md`, `AGENTS.md`, and `experiment-matrix.yaml` first.

## Mission

Prepare and execute a scientifically defensible, reproducible E0–E13 programme using this local repository and Codex CLI. The current task is to orchestrate; do not assume experiments have already been run. Start with Gate 0 only. Do not jump directly to expensive or live experiments.

## Hard constraints

- Preserve all historical files and results. Treat `data/`, `results/`, `data/llm_records/`, and `docs/RESULTS.md` as read-only for this orchestration.
- Do not run `reproduce.sh` or `experiments/run_all.py` until you have inspected every output side effect and established a baseline hash inventory.
- All new execution outputs go under a unique `results/runs/<run_id>/`. Never overwrite a run.
- Do not use production credentials, real accounts, external write actions or unapproved paid APIs.
- Never invent results, citations, proof obligations, or successful tool calls.
- Preserve failed runs and partial logs.
- Do not change paper claims until independent verification is complete.

## First assignment: Gate 0

1. Capture current branch, HEAD, dirty state, remotes (redact credentials), OS, Python, Codex CLI version and dependencies.
2. Inventory tracked files and hash historical results/data/LLM records.
3. Inspect experiment entry points and every write target in the scripts.
4. Map E0–E7 to actual code and data files; identify mismatches between README and implementation.
5. Produce `research-lab/reports/GATE0_BASELINE.md` and an immutable inventory under `research-lab/baselines/<commit-sha>/`.
6. Do not modify source, datasets, historical results or manuscript files.

## Agent orchestration

If Codex's active runtime explicitly supports subagents, delegate the eight roles in `research-lab/AGENTS.md` with bounded scopes and independent deliverables. Otherwise, tell the PI that multi-agent delegation is unavailable in this runtime and execute role reviews as separate Codex CLI sessions in isolated Git worktrees. Do not claim independent review if the same context performed both authoring and auditing.

## After Gate 0

Stop and report:
- baseline commit and cleanliness;
- historical path inventory and hashes;
- identified script side effects;
- exact E0–E7 entry points;
- blockers and required PI decisions;
- proposed Gate 1 worktree/branch plan.

Wait for PI approval before changing implementation, running long experiments, connecting live MCP servers, or incurring external costs.
