# Revision 2 plan — from the TSC experimental review to executed evidence

Status 2026-11-08. Branch `research/pamcp-final-evaluation`. This plan builds on the **Revision 1** package already on the
branch (`paper/revision_1/`, `experiments/revision_1/`: evidence ledger, point-by-point response, X1–X8 protocol, label
overlap audit, scope-aware E14 re-analysis, sanitiser audit). Revision 1 corrected claims and analysis; this plan is
about producing the missing evidence. The X1–X8 protocol and its completion gates in
`paper/revision_1/EXPERIMENT_PROTOCOL.md` are the reference; nothing here relaxes them.

## 1. The review, checked against the code

Every code-level observation of the review is correct:

| Reviewer observation | Where | Verdict |
|---|---|---|
| Unsafe set of $J_B$ ⊆ that of $J_A$; verifier simulated from $J_A$ | `e04_e07_exposure.py:42-62`; audit: subset true, κ = 0.944 | valid: zero exposure at FAR 0 holds by construction |
| Sanitised-manifest exposure set to zero | `e14_e18_factorial.py:102-107` | valid |
| Tamper dropped when a task needs any effect | `e14_e18_factorial.py:30-37` | valid |
| F5 treats task × attack pairs as independent | `e22_statistics.py:125` | valid |
| E5 at δ = 0 has one seed | `e04_e07_exposure.py:233` | valid |
| Evaluator simplifications (collections, fixed model kinds, flow, effect classes, coarse kinds) | `set_evaluator.py` | valid |
| Calibration: 64 items, 4 classes, ceiling for Sonnet and Opus | `E12_profile.json` | valid |
| QoS defaults make η, ζ inert | `contracts.py:177` | valid |
| Near-duplicate clones; eager quadratic pair relation | `e15_e16_scale_evolution.py:36`, `hypergraph.py:164` | valid |

## 2. Results of running the Revision 1 scripts (run here, 2026-11-08, not yet committed by CI)

The Revision 1 README marks its scripts as "pending execution". They run without error in this environment
(`pytest experiments/revision_1/test_scope_policy.py`: 6 passed):

* **Label overlap**: $U_B \subseteq U_A$ confirmed; binary κ 0.944.
* **Sanitiser audit**: the current `sanitise()` rebuilds descriptions (0 of 569 description canaries leak) but keeps
  provider-controlled tool names and argument keys: the name canary leaks in 569 of 569 tools, the argument-key canary
  in 517. The alias-manifest prototype leaks none, but it is not wired into the engine.
* **Scope-aware E14** (exploratory): full PaMCP has no definite out-of-scope action, but 25.2% of tasks have an
  *indeterminate* one (labels without a scope), against 8.4% definite for NoCert; task-level difference full PaMCP minus
  unfiltered per-subtask −0.168, 95% CI [−0.239, −0.097]. The earlier "0 of 712" therefore holds only for definite
  violations under class-level labels.

## 3. Issues neither the review nor Revision 1 covers

| # | Issue | Evidence | Fix |
|---|---|---|---|
| A1 | The 60 development prompts used to select K and $w_{rel}$ (`experiments/e3_tune.py:23`) are 60 of the 155 tasks of E14, E17, E18, E20 and of the Revision 1 scope-aware E14 | `fe.tasks_dev`; `e14_e18_factorial.py` docstring | report on the 95 test tasks; dev separately |
| A2 | Confirmatory F4 (verified vs lexical Exp@5) is uninformative: its verified side is zero by construction | `E22_statistics.json` | remove from the confirmatory family in the dated amendment |
| A3 | E10's S check decides from $J_B$'s types, so joint feasibility largely measures $J_B$–τ agreement (S passes 68%) | `set_evaluator.py:serves` | report E10 with oracle types too (X3 J) |
| A4 | *done*: E15 optimality gap was computed on price + latency + 1, not on the searched objective | `E15_optimality_gap.json` | new values 0.7 / 2.3 / 14.5% |
| A5 | *done*: two results depended on Python's hash seed (E22 split, a greedy tie in E15) | `e22_statistics.py:50`, `composer.py:188` | E22 stratified τ 0.683 |
| A6 | Revision 1's E14 re-analysis keeps the dev prompts (A1) | `reanalyse_e14_scope_aware.py` input | filter to test tasks |
| A7 | The experience repository exists (`manifest.py:55-79`) but the request path never consults it | `engine.py` | wire in before X8 |
| A8 | The alias manifest closes the name and argument-key leak but is only a prototype | sanitiser audit | integrate into `manifest.py`; re-run the audit end to end |

## 4. What can be executed, and where

| Code | Meaning |
|---|---|
| **C** | computation here, no new LLM output |
| **L** | new LLM outputs here (Claude Haiku / Sonnet / Opus; recorded and replayed; version strings not exposed, alias and date recorded) |
| **X** | executed MCP servers here, small scale: credential-free local servers (MCP reference servers from npm, Python `mcp` SDK) and adversarial servers we write |
| **A** | authors only: human annotators; GPU and Hugging Face access (HTTP 403 here, so no BGE-M3, cross-encoders or PLM fine-tuning); credentials; other model providers |

| Protocol item | Here | What is done here | Left to the authors |
|---|---|---|---|
| X1 contract and effect ground truth | C, A | 200-tool stratified sample (reviewer strata), blind annotation sheet, guide, adjudication and analysis scripts | two annotators, adjudicator |
| X2 runtime effects and provenance | X | sandboxed probing (temporary filesystem, SQLite, process and network monitoring) of every credential-free tool that runs locally, bound to the definition hash; observed-effect labels; verifier FAR/FRR and $J_A$/$J_B$ accuracy against them with Wilson and server-cluster intervals; adversarial servers for forged annotations, poisoned names and descriptions, rug pulls, malicious returns | credentialed servers |
| X3 retrieval and typing | C, A | conditions BM25, dense, lexical+dense, current, relevance-first, confidence-gated (labels A carry `sure`), oracle goal types (gold tool's $J_B$ type), oracle tool types ($J_B$); Hit@1/3/5, MRR, nDCG, group recall; strata by registry size, type confidence, tool- and server-disjoint splits; every baseline tuned on the 60 dev prompts with the same grid budget; PaMCP-v2 chosen on dev, tested once | human-corrected types (after X1); official COLT/ToolScope/BGE-M3 on GPU |
| X4 scope-aware static security and manifest | C | A6 fix; alias manifest integrated (A8); manifest canary scan on the manifests the pipeline actually returns; task-clustered statistics and a mixed-effects model | — |
| X5 executable composition | X, L | 30–60 multi-step tasks over local servers with independent artifact validators; same Claude agent and budget for all systems; full logging per the protocol; certificate validity and task success reported separately | larger, credentialed benchmark |
| X6 QoS | C | controlled alternatives with differentiated price, latency, failure, capacity; exact Pareto set or ILP (SciPy/HiGHS) on tractable instances | measured third-party QoS |
| X7 scale and evolution | C | eager / lazy / effect-partitioned / incremental / on-demand risk relation (toolkits must stay identical on E9, E10, E14); heterogeneous generator (servers, tools per server, duplicates, annotation sparsity, effect mix, shared types, forbidden-pair density, update rate); real subsamples 100–569; concurrent requests | real heterogeneous snapshots beyond 569 tools |
| X8 refinement and reuse | C, L | A7 wiring; reuse under stale registry, changed model, changed principal, revoked tool, changed hash; repair arms none / deterministic / LLM without certification / LLM with re-certification / oracle | — |
| Model profile (review M11) | L, A | about 1,000 items: seven operation classes × sizes × English and multilingual × difficulty × exactness × input quality × context; held-out split; three Claude models; ECE, Brier, reliability, selective risk, false-native rate; τ from an explicit risk target | other providers |
| Statistics (review M9) | C | E5 δ = 0 with five seeds; target-tool and task clustering everywhere; effect sizes, units and n for every test; statistics appendix; dated amended preregistration (F4 dropped, new family) committed before any X2–X5 run | — |
| Lineage (review 4.5) | C | one row per Section 8 number: input hashes → commit → config → raw records → aggregate → table or figure | — |

## 5. Order and gates

| Step | Content | Codes | Gate before the next step |
|---|---|---|---|
| 1 | Commit Revision 1 outputs; fix A1, A6; integrate alias manifest (A8) and rerun the sanitiser audit on real manifests; E5 seeds; clustered statistics; lineage | C | — |
| 2 | X3 on dev: choose PaMCP-v2 and tune all baselines on dev only | C | dev-only decisions written down |
| 3 | Amended preregistration: hypotheses, units, margins, family (without F4) | text | committed and pushed before step 4 |
| 4 | X3 on test, X4, X6, X7, X8-reuse, E10 with oracle types | C | — |
| 5 | Model profile suite, X8 LLM repair, re-typing of poisoned tools | L | — |
| 6 | X2 probing and adversarial servers; X5 executed tasks | X, L | sample-size check: if n is small, report as a feasibility study |
| 7 | X1 human annotation, then re-scoring of E1–E4, E8–E10, E14 against it; GPU baselines; other providers | A | — |
| 8 | Section 8 rewritten by hypothesis and evidence class; answers Q1–Q12 with results; notebook extended to the new series | text | every number traced (lineage) |

## 6. Risks

* PaMCP-v2 may not recover retrieval quality; the paper is then positioned as the review suggests, on pre-execution
  certification and its evidence assumptions.
* The executed benchmark (X2, X5) will be small and local; it supports feasibility, not performance at scale.
* LLM-based steps keep the version-string limitation.
* Human annotation (X1) is on the critical path for Q1 and Q4; it cannot be produced here.
* The branch is edited concurrently (Revision 1 CI commits `results/revision_1/`): pull before every push.
