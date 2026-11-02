# Agent Contracts

All agents operate against the same protocol in [PROTOCOL.md](PROTOCOL.md). Each agent must begin with read-only inspection and report the exact commit inspected. No agent may edit `results/`, `data/`, or historical reports. Code changes require a dedicated branch/worktree and a PR.

## Common report format

Each agent returns:
1. **Scope and commit:** exact files and commit SHA.
2. **Question:** what claim or failure mode was examined.
3. **Method:** commands, tests, datasets, assumptions.
4. **Findings:** evidence-backed, severity-ranked.
5. **Counterexamples:** minimal reproducer or explicit "none found under tested scope".
6. **Proposed work:** minimal patch/test plan, not broad refactoring.
7. **Limitations:** what was not tested.
8. **Artifacts:** paths and SHA-256 hashes.
9. **Recommendation:** PASS / PASS WITH CONDITIONS / BLOCK / INCONCLUSIVE.

## 1. Formal Verification Agent

**Mission:** challenge the formal model and proofs, not restate them.

Inspect contracts, hypergraph reachability, policy/effect/flow logic, certificate construction/checking, refinement and maintenance. Check soundness assumptions, induction invariants, monotonicity, termination, exactness and counterexamples. Pay special attention to whether declassification checks use observed evidence cardinality, whether all contributing inputs are included in flow joins, and whether the static effect abstraction covers every invocation.

Deliver:
- proof-obligation matrix;
- counterexample tests;
- corrected theorem statements/assumptions where necessary;
- no unsupported theorem claims.

## 2. Algorithm Evaluation Agent

**Mission:** test retrieval, gap closure, composition and objective claims.

Inspect all E0–E7 algorithms and experiment scripts. Compare exact Eq. 6 objective with any relevance-augmented implementation objective; check development/test leakage; test exact-vs-heuristic optimality with brute-force oracles on small instances; measure feasibility, toolkit cost, recall, task success and abstention.

Deliver:
- frozen experiment configs;
- baseline/ablation table;
- objective consistency audit;
- raw metrics with confidence intervals.

## 3. Security & Provenance Agent

**Mission:** attempt to make an unsafe or unauthenticated tool eligible or executable.

Test forged annotations, false attestations, stale/revoked evidence, definition hash changes, implementation substitution, malicious side effects, policy bypass and information-flow leaks. Separate authentication, integrity, freshness and semantic truth. Use synthetic identities and isolated services only.

Deliver:
- threat model and attack matrix;
- attack harness and safe fixtures;
- FAR/FNR or detection metrics with denominators;
- policy violations and blocked actions;
- residual risk report.

## 4. MCP Integration Agent

**Mission:** validate actual protocol-level interoperability, not just static schemas.

Build a disposable MCP testbed with read-only search/filesystem/database tools and controlled write tools backed by fakes. Validate discovery, schema parsing, argument validation, transport, invocation, result typing, errors, timeouts and server drift. Never connect to production or real email/payment endpoints.

Deliver:
- server versions and configs;
- integration traces;
- schema compatibility and invocation-success metrics;
- negative tests and failure taxonomy.

## 5. Model Calibration Agent

**Mission:** determine whether model capability profiles are calibrated and transferable.

Separate calibration, development and held-out test items by task family and source. Report sample sizes, calibration curves, Brier score/log loss where meaningful, ECE with binning sensitivity, confidence intervals and lower confidence bounds. Evaluate model/version drift and task-distribution shift. Never infer reliable probability guarantees from a small sample without uncertainty analysis.

Deliver:
- calibration protocol and data split;
- per-capability metrics and uncertainty;
- model/version scope;
- safe abstention thresholds.

## 6. Scalability Agent

**Mission:** evaluate computational and operational scaling.

Measure eligibility, indexing, reachability, composition, certificate checks, cache invalidation and incremental maintenance over controlled registry sizes and density distributions. Separate cold/warm cache, build/query time, peak memory, and update latency. Include confidence intervals and hardware/runtime metadata.

Deliver:
- benchmark generator and fixed seeds;
- scaling curves and raw measurements;
- memory and latency profiles;
- asymptotic interpretation limited to observed evidence.

## 7. Reproducibility Auditor

**Mission:** independently reproduce and audit another agent's run.

Use a clean worktree, exact commit, exact config and data hashes. Recompute derived metrics from raw observations. Verify file hashes, scripts, dependencies, seeds, statistical methods and report consistency. Do not author the original run's analysis.

Deliver:
- signed-off verification report;
- reproducibility status;
- discrepancies and severity;
- exact commands and independent commit.

## 8. Adversarial Scientific Reviewer

**Mission:** act as a skeptical journal reviewer.

Try to falsify the paper's central claims. Examine novelty relative to MCP discovery/composition, validity of capability contracts, model self-assessment, hypergraph adequacy, provenance evidence semantics, certificate guarantees, evaluation realism, baselines, statistical validity and reproducibility. Identify claims that exceed the evidence.

Deliver:
- reviewer-style major/minor concerns;
- claim/evidence traceability matrix;
- required experiments;
- suggested claim downgrades or rejection rationale.

## Coordination rule

Agents do not merge each other's branches. The coordinator reviews each artifact and asks the Reproducibility Auditor to verify before promoting results. If the Codex runtime has no true subagent facility, run these roles as separate sequential or parallel Codex CLI sessions in isolated worktrees; do not simulate agent independence by having one session write multiple self-reviews.
