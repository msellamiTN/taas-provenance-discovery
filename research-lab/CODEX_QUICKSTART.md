# Codex Quick Start

## 1. Get the orchestration branch

From an existing local clone:

```bash
git status --short
git fetch origin
git switch --track origin/codex/experiment-orchestration-v1
```

If the branch is already present locally:

```bash
git switch codex/experiment-orchestration-v1
git pull --ff-only
```

Do not proceed with a dirty worktree. Commit or stash unrelated work first; do not discard it.

## 2. Check the runtime

```bash
git rev-parse HEAD
git status --porcelain
python --version
codex --version
```

The coordinator must record these values in the Gate 0 report. If the installed Codex version does not support delegated subagents, use separate Codex sessions and isolated worktrees; do not claim parallel independent review from a single session.

## 3. Start the coordinator

From the repository root:

```bash
codex
```

Paste the complete contents of `research-lab/prompts/COORDINATOR.md`. The first run is read-only Gate 0. The coordinator must stop after producing the baseline inventory and report.

For a non-interactive Codex CLI run, use the prompt file as input only if supported by the installed CLI version; check `codex exec --help` first. Do not assume CLI flags from another version.

## 4. Multi-agent execution

If delegated subagents are supported and enabled, launch one bounded role from `research-lab/AGENTS.md` per agent. Give each agent:
- the exact baseline commit SHA;
- one role and bounded file scope;
- a read-only-first instruction;
- a separate output report path;
- an explicit prohibition on modifying historical data/results.

If delegated subagents are not available, create a separate worktree for each code-changing workstream. Example:

```bash
git worktree add ../taas-formal-review -b review/formal-verification <BASELINE_SHA>
git worktree add ../taas-security-review -b review/security-provenance <BASELINE_SHA>
```

For read-only reviews, separate sessions may use the same commit but should still write reports to distinct paths/branches. Never have multiple sessions edit the same checkout concurrently.

## 5. Run and review

Do not launch E0–E13 until Gate 0 is complete and the PI approves the frozen experiment plan. Each experiment writes to a unique `results/runs/<run_id>/` directory. Validate a completed evidence bundle with:

```bash
python scripts/validate_run_bundle.py results/runs/<run_id>
```

The validator checks manifest structure and hashes only. An independent auditor must still reproduce the analysis before status can become `VERIFIED`.

## 6. Pull request

The orchestration files are proposed in [PR #1](https://github.com/msellamiTN/taas-provenance-discovery/pull/1). Do not merge automatically; review the protocol and branch contents first.
