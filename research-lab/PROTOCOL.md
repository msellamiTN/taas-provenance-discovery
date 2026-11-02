# Codex Multi-Agent Experiment Orchestration Protocol

## 1. Objective and scope

Operate a reproducible research laboratory for *Tool-as-a-Service: Provenance-Aware Tool Discovery for LLM Agents in MCP Ecosystems*. The goal is to independently inspect and reproduce the existing E0–E7 study, then execute well-scoped extensions E8–E13. The protocol must expose scientific weaknesses, not merely produce favourable numbers.

The current repository README documents important limitations: LLM silver labels rather than independent ground truth; simulated verifier false-accept rates; no real MCP server execution in the reported study; gold-tool recall rather than end-to-end task success; synthetic typed-interface composition experiments; and a relevance term tuned on development data. These limitations are experimental facts to retain in the interpretation, not problems to hide.

## 2. Runtime and topology

**Primary runtime:** Codex CLI, started from a local clone of this repository.  
**Coordination source of truth:** Git branches, commits, task files, run manifests and review reports.  
**Execution workspace:** local clone plus isolated Git worktrees.  
**Remote mirror:** GitHub repository `msellamiTN/taas-provenance-discovery`.

Use Codex multi-agent delegation only if the installed Codex runtime explicitly supports it and the user has enabled it. Otherwise emulate parallelism with independent Codex CLI sessions, each in a dedicated Git worktree and assigned a single role contract. Never assume that multiple agents can safely edit one shared checkout.

### Recommended roles

- Principal Investigator / Coordinator: schedules work, controls gates, integrates reviewed results.
- Formal Verification: proof obligations, counterexamples, invariant/property tests.
- Algorithm Evaluation: baselines, ablations, objective/optimality, task success.
- Security & Provenance: forged/stale evidence, policy attacks, definition substitution.
- MCP Integration: real protocol interoperability in an isolated testbed.
- Model Calibration: calibration split design, uncertainty bounds, distribution shift.
- Scalability: runtime, memory, update costs, scale-up experiments.
- Reproducibility Auditor: clean rerun, hashes, statistics, artifact audit.
- Adversarial Scientific Reviewer: attempts to falsify claims and identify overstatement.

The coordinator is the only role allowed to integrate patches or update aggregate claims in the paper.

## 3. Phase gates

### Gate 0 — Repository and baseline inventory (read-only)

1. Record `git status --porcelain`, current branch, HEAD SHA, remote URLs (redact credentials), Python/runtime versions, OS and dependency lock state.
2. Inventory all tracked files under `experiments/`, `results/`, `data/`, `docs/`, `tests/`, and `src/`.
3. Hash historical result artifacts and key data files into a baseline inventory stored outside historical paths, e.g. `research-lab/baselines/<baseline_sha>/inventory.json`.
4. Read `reproduce.sh`, `experiments/run_all.py`, all experiment entry points and report/plot scripts to identify every output path and destructive side effect.
5. Run no experiment and change no source file at this gate.

**Exit:** baseline inventory committed or archived; no historical file changed; experiment dependency graph and runtime requirements documented.

### Gate 1 — Static scientific and implementation audit

Each specialist reviews a bounded area and submits:
- files/commit inspected;
- claims and code paths checked;
- concrete counterexamples or proof obligations;
- severity (BLOCKER / MAJOR / MINOR / NOTE);
- proposed minimal tests;
- whether the issue blocks a particular experiment.

Review at least: provenance/evidence admission, declassification thresholds, flow propagation across all inputs, model profile calibration, closed-world assumptions, interface compatibility, certificate semantics, runtime-vs-static guarantees, objective consistency, cache invalidation, and refinement termination.

Do not patch the implementation in the same branch used to report a finding. A finding must include a failing test or a precise executable counterexample wherever feasible.

### Gate 2 — Reproduction plan and safety review

For each E0–E13 experiment, freeze:
- research question and falsifiable hypothesis;
- unit of analysis and sampling frame;
- dataset version and SHA-256 fingerprints;
- inclusion/exclusion criteria;
- independent ground truth source and annotation protocol;
- baselines and ablations;
- primary and secondary metrics;
- statistical analysis plan and confidence intervals;
- random seeds and number of repetitions;
- resource budget and expected runtime;
- side effects, network access and secrets required;
- expected output schema and acceptance criteria.

A live MCP integration test must use a disposable, isolated environment, least-privilege credentials, allowlisted endpoints, fake/simulated accounts, and explicit operator approval. Default mode is offline.

### Gate 3 — Controlled execution

1. Start from a clean, recorded commit.
2. Create a unique run ID: UTC timestamp + short commit SHA + experiment code.
3. Create a dedicated run directory `results/runs/<run_id>/`; never reuse a populated directory.
4. Save configuration before execution.
5. Save stdout and stderr separately; record exit status and wall-clock duration.
6. Save raw observations before aggregation or plotting.
7. Record all input and output hashes, package versions, hardware, OS, Python version, seeds, model/API identifiers and any cost.
8. Never manually edit raw observations. Corrections create a new run and retain the old one.
9. On failure, preserve partial logs and mark FAILED or BLOCKED; do not silently retry into the same directory.

### Gate 4 — Independent verification

The Reproducibility Auditor must rerun the experiment from a clean worktree or independently execute the analysis from raw observations. Verify:
- commit and dataset fingerprints match the manifest;
- scripts/configs are sufficient to regenerate the result;
- raw-to-summary transformation is deterministic or its nondeterminism is quantified;
- statistical calculations and uncertainty intervals are correct;
- plots are generated from raw or documented derived data;
- no output was copied from historical results;
- reported claims match the observed data.

Only then set status to VERIFIED and add auditor identity, commit, date, and verification notes. A failed rerun remains visible and is reported.

### Gate 5 — Integration and manuscript update

Integrate agent work through reviewed PRs. Preserve historical results. New aggregate reports must identify their run IDs and distinguish reproduced, extended, simulated, synthetic, and blocked evidence. Manuscript claims are updated only after Gate 4.

## 4. Run evidence contract

Every run directory must contain at least:

```text
results/runs/<run_id>/
  run_manifest.json
  config/
    experiment.yaml
  logs/
    stdout.log
    stderr.log
  raw/
    observations.jsonl       # or a documented equivalent
  derived/
    metrics.json
    tables/
    figures/
  reports/
    execution_report.md
    verification_report.md   # added by independent auditor
```

The manifest schema is intentionally strict about provenance and flexible about experiment-specific metrics. Required top-level fields:

- `schema_version`
- `run_id`
- `experiment_id`
- `status`
- `started_at_utc`, `finished_at_utc`
- `git_commit`, `git_branch`, `working_tree_clean`
- `environment` (OS, Python, Codex CLI version, dependencies, hardware)
- `dataset_fingerprints`
- `config_path`, `config_sha256`
- `seed` (or explicit `null` with reason)
- `command`, `exit_code`
- `artifacts`: array of relative paths and SHA-256 values
- `limitations`, `deviations`, `costs`
- `verification`: state, auditor, date, commit, notes

The validator checks structural completeness and hashes; it does not prove scientific validity.

## 5. Experiment sequence

Run in this order unless the PI documents a dependency-based reason to change it:

1. E0 baseline/data integrity and exact registry counts.
2. E1 baseline pipeline / scenario consistency.
3. E2 provenance eligibility and false-accept sensitivity.
4. E3 model-conditioned capability gap and retrieval comparisons.
5. E4 certificate/effect-safety counterexamples and call-order tests.
6. E5 composition feasibility and exact-vs-heuristic optimality.
7. E6 relevance-term ablation and held-out evaluation.
8. E7 scale, cache invalidation and incremental maintenance.
9. E8 real MCP interface interoperability.
10. E9 runtime policy and information-flow enforcement.
11. E10 provenance attacks and definition substitution.
12. E11 model capability calibration and distribution shift.
13. E12 dynamic registry, evidence revocation and certificate freshness.
14. E13 multi-objective composition and Pareto/optimality analysis.

E0–E7 first run in historical-reproduction mode, writing only to new run directories. If an old script writes into historical paths, wrap or adapt it in a non-invasive copy/branch before running.

## 6. Scientific validity rules

- Distinguish tool-level eligibility, toolkit-level certificate validity, runtime trace safety, and end-to-end task success.
- Distinguish schema compatibility from successful invocation and correct semantics.
- Distinguish evidence authenticity, integrity, freshness, and truth/adequacy.
- A signed statement is not automatically true; sandbox evidence is bounded by tested inputs, permissions, environment and implementation identity.
- Missing evidence is UNKNOWN, not proof of absence of an effect.
- Model capability estimates require independent calibration, uncertainty intervals and explicit distributional assumptions.
- A static certificate is only a sufficient pre-execution guarantee under its declared abstraction assumptions. Runtime safety claims require an enforcement point that checks every invocation and relevant state.
- Exact optimality is claimed only when the exact solver terminates with a valid optimality proof. Heuristic solutions report gaps or no optimality claim.
- The benchmark's silver labels must not be described as ground truth. Report inter-annotator/independent validation where available.
- Report abstentions, infeasible tasks, failed invocations and negative results.
- No post-hoc tuning on test data. Freeze a development/test split before tuning.
- Report confidence intervals and effect sizes, not only point estimates. Correct for multiple comparisons when applicable.

## 7. Stop conditions

Stop and escalate to the PI if:
- a run would modify historical result/data files;
- real external side effects or production credentials are required;
- an experiment depends on a disputed formal assumption;
- data provenance or licensing is unclear;
- the implementation differs materially from the manuscript;
- a result cannot be traced to raw observations;
- the environment is not isolated for a security test;
- a task requires new API spend or external data access not approved.

## 8. Definition of done

The orchestration is complete only when every planned experiment has a state, every executed run has an evidence bundle, every VERIFIED run has an independent audit, all failures/deviations are visible, and the paper's claims are traceable to verified run IDs. A green test suite alone is not completion.
