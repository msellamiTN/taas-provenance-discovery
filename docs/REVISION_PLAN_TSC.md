# Revision plan in response to the TSC experimental review of PaMCP

Status: plan, 2026-11-08. Branch `research/pamcp-final-evaluation`. Every statement about the code below was checked
against the source on this branch (file and line given). Nothing in this plan has been run yet unless marked *done*.

## 0. Assessment of the review

The review is accurate. Every code-level observation it makes was verified:

| Reviewer observation | Verified in the code | Verdict |
|---|---|---|
| Unsafe set of $J_B$ ⊆ unsafe set of $J_A$; verifier simulated from $J_A$ | `e04_e07_exposure.py:42-62` draws verifier decisions from labels A; 120 ⊆ 131 | valid; zero exposure at FAR 0 is a consequence of the construction |
| Sanitised-manifest exposure is zero by construction | `e14_e18_factorial.py:102-107`: `poison_shown = 0.0 if sanitised` | valid; the manifest was never given poisoned text |
| Tamper attacks dropped when a task needs any effect | `e14_e18_factorial.py:30-37` (`if a == "tamper" and need: continue`) | valid; attacks are effect classes, not scoped actions |
| F5 tests task × attack pairs as independent | `e22_statistics.py:125` | valid; clustering by task ignored |
| E5 at δ = 0 has one seed | `e04_e07_exposure.py:233` (`range(5 if delta > 0 else 1)`) | valid |
| Evaluator: collections ignored, fixed model kinds, flow = private + egress_any, effect classes, coarse output-kind equality | `set_evaluator.py` (`_kind`, `MODEL_KINDS`, `serves`, `flow_bad`) | valid; the evaluator is separate code, not an independent oracle |
| Calibration: 64 items, 4 classes × 4 sizes; Sonnet and Opus at ceiling | `results/final/E12_profile.json` | valid |
| QoS defaults make η, ζ inert | `contracts.py:177` (`qos or QoS()`), E20 | valid |
| E15 clones are near-duplicates; eager quadratic pair relation | `e15_e16_scale_evolution.py:36`, `hypergraph.py:164-170` | valid |
| E17 deterministic repairs only; E21, E13 not run | ledger | valid |
| Model version strings not recorded | manifests | valid; cannot be recovered for past runs |

Our own audit adds issues the reviewer did not raise:

| # | Issue | Evidence | Consequence |
|---|---|---|---|
| A1 | The 60 development prompts used to select K and $w_{rel}$ (`experiments/e3_tune.py:23`) are 60 of the 155 tasks of E14, E17, E18 and E20 | `fe.tasks_dev`, `e14_e18_factorial.py` docstring | dev/test leakage in those series; report on the 95 test tasks, dev separately |
| A2 | Confirmatory test F4 (verified vs lexical Exp@5) is uninformative: its verified side is zero by construction (A0) | `E22_statistics.json` F4 | F4 must leave the confirmatory family (dated amendment) |
| A3 | E10's S check is decided from $J_B$'s types, so joint feasibility largely measures agreement between $J_B$ and τ (S passes 68%) | `set_evaluator.py:serves` | E10 measures label agreement as much as composition quality |
| A4 | *done*: the E15 optimality gap was computed on price + latency + 1, not on the objective the search minimises | fixed: `E15_optimality_gap.json` uses Eq. (6) | numbers change: 0.7%, 2.3%, 14.5% |
| A5 | *done*: two results depended on Python's hash seed (E22 split stability; one greedy tie in E15) | fixed: sorted iteration (`e22_statistics.py:50`, `composer.py:188`) | E22 stratified τ 0.688 → 0.683 |
| A6 | Section 8 text states that the sanitised manifest "shows none of the poisoned descriptions"; that is the by-construction value of A0 | `evaluation_final.tex`, E14 paragraph | sentence must go until 1.3 is run |
| A7 | The experience repository exists (`manifest.py:55-79`) but is not wired into the request path | `engine.py` has no pattern lookup | E21 needs integration before it can be measured |

Overall: the review's diagnosis stands, and the strategy it recommends (repair validity first, then the retrieval weakness,
then execution evidence, then rewrite the narrative) is the right order. Two of its requests go beyond one paper and are
scoped down below: the full ten-variant retrieval matrix includes human-corrected typing (needs annotators), and
"multiple independently versioned models" needs providers other than the one available to these experiments.

## 1. Where each fix can be done

| Code | Meaning |
|---|---|
| **C** | computation only, in this environment, no new LLM output |
| **L** | needs new LLM outputs; possible here with Claude Haiku, Sonnet and Opus (recorded and replayed like the existing ones; exact version strings are not exposed) |
| **X** | needs executed MCP servers; possible here at small scale with credential-free local servers (MCP reference servers install from npm, the `mcp` SDK from pip) and adversarial servers we write |
| **A** | needs the authors: human annotators, GPU and Hugging Face access (blocked here: HTTP 403, so no BGE-M3, cross-encoder or PLM fine-tuning), credentials for third-party servers, other model providers |

## 2. Plan per reviewer comment

### Critical 1 / Major 1 — safety results coupled to the labels
* **1a (C)** Label-swap and disagreement analysis: simulate the verifier from $J_B$ and score against $J_A$; report exposure on the 11
  tools where the labellings disagree; place verifier errors on those tools. Quantifies how much of the safety result is
  a labelling artefact. Re-run E4–E7 (13 min).
* **1b (X)** Observed effects for every runnable, credential-free server in the registry plus our adversarial servers: run each tool
  in a sandbox (temporary filesystem, SQLite, process and network monitoring), record observed effects. Gives a third,
  non-LLM reference on a subset; compute verifier FAR/FRR and $J_A$/$J_B$ accuracy against it with Wilson CIs.
* **1c (A)** Human labels (see Major 4) as the independent reference for FAR/FRR on 150–200 tools.
* **1d (C)** Server-level and tool-level partitions: cluster bootstrap by server for every exposure estimate.
* **Text** Zero exposure becomes "zero by construction of the simulation"; Property 1 stated as conditional on truthful
  evidence; F4 removed from the confirmatory family (A2).

### Critical 2 / Major 2 — no end-to-end execution (E13)
* **2a (X+L)** Executable composition benchmark at small scale: 30–60 multi-step tasks over local servers (filesystem, memory,
  SQLite, git, time, a local mail/chat sink, our adversarial servers), each with a deterministic checker for the final
  artifact. The agent is a Claude model driving a call harness that logs every call, argument, result and effect. Arms:
  PaMCP, retrieval-only (RAG-MCP, MCP-Zero), eligible retrieval, full catalogue. Metrics: the reviewer's table
  (end-to-end success, composition success, argument validity, call completion, policy and flow violations observed,
  abstention correctness, recovery, latency, cost). Certificate validity and task success reported separately.
* **2b (A)** Larger benchmark with credentialed third-party servers.
* **Limit to state** Local servers only, one model provider, small n.

### Critical 3 / Major 3 — retrieval weakness (E8)
* **3a (C)** E8-R controlled diagnosis on the 300-query sample and the distractor curve: A lexical, B dense, C lexical+dense, D structural only,
  E current fusion, F relevance-first with type re-ranking, G confidence-gated typing (labels A carry a confidence `sure`),
  I oracle goal types (goal type := the gold tool's $J_B$ output type), J oracle tool types ($J_B$ instead of τ). H
  (human-corrected typing) waits for 4a. Metrics Hit@1/3/5, MRR, nDCG@5/10, recall, by registry size and by
  type-confidence band; target-tool clustered CIs.
* **3b (C)** Architectural variant chosen on the 60 dev prompts only (structure as a confidence-weighted re-ranker or a
  feasibility filter applied after relevance), then evaluated once on test (E8, E9, E10) as "PaMCP-v2", with the
  current variant kept and reported.

### Critical 4 / Major 4 — no independent ground truth
* **4a (A)** Human annotation of 200 tools stratified by server, effect class, semantic type, annotation availability, read-only vs
  state-modifying, evidence availability and schema completeness; two annotators, adjudication; Cohen's κ, Krippendorff's α,
  macro-F1, per-class P/R, scoped-effect and domain-type agreement, confidence calibration. The 150-item sheet
  (`docs/annotation/E2_human_annotation_sheet.csv`) is extended to 200 with the reviewer's strata; guide, sheet and
  analysis script are prepared here (**C**).
* **4b (C, after 4a)** Re-score E1–E4, E8–E10, E14 against the human subset.
* **4c (L)** A third labelling with a different prompt and model as a robustness check, reported as such (not ground truth).

### Critical 5 / Major 5 — baseline fairness
* **5a (C)** Equal tuning budget: every baseline tuned on the same 60 dev prompts with the same grid size as PaMCP (RAG-MCP k;
  MCP-Zero server and tool budgets; COLT λ, μ; ToolScope α and merge threshold; CMTF depth and per-goal width).
* **5b (C)** Equal information: table of what each method receives (registry fields, decomposition, LLM outputs, dev data,
  candidate budget, encoder); variants of baselines given the analyst's decomposition where PaMCP has it.
* **5c (C)** Oracle baselines: gold decomposition (gold tools' types) and correct tool types ($J_B$), for all methods.
* **5d (A)** Faithful reproductions with official code and models (COLT with PLM fine-tuning, ToolScope with its
  cross-encoder, BGE-M3 for everyone); scripts prepared here, run on the authors' GPU machine. Reported as a second
  baseline family next to the controlled adaptations.

### Major 6 — composition advantage not established
* **6a (C)** Quality–risk–cost frontier from E9, E10, E14: recall, joint feasibility, reachable attacks, size, tokens at budgets
  k = 1…10 and token budgets; equal-size, equal-token and equal-safety-budget comparisons; task-level feasibility.
* **6b** Separate gold recall, functional sufficiency, minimality, policy compliance and (from 2a) executed success.
* **Text** Remove any implication that PaMCP improves overall composition quality.

### Major 7 — evaluator independence
* **7a (C)** Ten adversarial evaluator tests (the reviewer's list), written as unit tests with hand-built ground truth.
* **7b (C)** Evaluator variants: collection-aware kinds, domain-aware types, scoped effects; report E10 under each.
* **7c (X)** Validate the evaluator against executed traces from 2a.
* **Text** List which checks are exact and which approximate.

### Major 8 — E14 is offline reachability
* **8a (C)** Scoped attack specification $a$ = (operation, target scope, principal, data label, condition); a scoped write to
  `/reports` no longer authorises tampering elsewhere. Re-run E14/E18 (20 min).
* **8b (C)** Real sanitisation test: poison names, descriptions and argument defaults of sampled tools, rebuild contracts and
  manifests, and test whether injected strings survive (`manifest.py:sanitise` copies the tool name, sanitised to
  `[A-Za-z0-9_]`). **(L)** Re-type the poisoned tools to test whether injection reaches τ.
* **8c (X)** Executable attack suite (tool poisoning, rug pull, indirect injection, confused deputy, exfiltration to a local
  sink, destructive action, privilege escalation, multi-tool collusion) × arms (raw discovery, annotation filter, lexical
  filter, eligibility only, full PaMCP, full PaMCP + runtime enforcement), recording suggested / retrieved / exposed /
  selected / invoked / executed / blocked / detected.

### Major 9 — statistics
* **9.1 (C)** E5 at δ = 0 with five seeds; seed-level distributions for E5–E7.
* **9.2 (C)** Task-clustered analysis of E14 (task-level paired test and a mixed-effects logistic model, statsmodels).
* **9.3 (C)** Effect size, CI, test direction, unit and n for every comparison (table in the appendix).
* **9.4 Text** E22 split stability described as stability under resampling, not replication.
* **9.5 (C)** Target-tool clustering applied to every request-level comparison; task clustering to task-level ones.
* **Appendix (C)** Statistics appendix: hypotheses, units, clusters, exclusions, missing data, CI methods, multiplicity,
  seeds, sensitivity to the resampling unit, scripts. A dated amendment of the preregistration (new family for the
  revision) is fixed before any Phase 2–3 run.

### Major 10 — scalability
* **10a (C)** Pair relation: eager vs lazy vs effect-class partitioned vs incremental vs on-demand, implemented in the engine
  and checked equal on the existing tests and E9/E10/E14 (identical toolkits required).
* **10b (C)** Heterogeneous generator varying servers, tools per server, effectful share, missing annotations, shared
  intermediate types, forbidden-pair density; real-registry subsamples (100–569); concurrent requests; end-to-end latency
  and memory; insertion, deletion and update under load.
* **Text** Bitmap microbenchmark kept separate from full-engine scalability.

### Major 11 — calibration
* **11a (L)** Calibration suite of about 1,000 items: classification, extraction, synthesis, translation, aggregation, exact
  computation, conversion × sizes × English/multilingual × easy/ambiguous/adversarial × approximate/exact ×
  clean/noisy/incomplete × isolated/multi-step; held-out calibration and test split; three Claude models. Accuracy, ECE,
  Brier, reliability diagrams, selective risk vs coverage, false-native and false-tool-required rates; τ chosen from an
  explicit risk target.
* **11b (A)** Other providers for model independence; profile stability across version updates.

### Major 12 — QoS
* **12a (C)** Registries of interchangeable tools with differentiated price, latency, failure, capacity and availability;
  PaMCP vs exact Pareto set (enumeration or ILP); selected toolkits under weight and utility-floor sweeps.
* **Text** Until then: QoS is a supported capability, not a validated advantage.

### Major 13 — optimality
* **13a (C)** Instance families varying candidate density, alternative producers, arity, depth, conflicts, shared tools, QoS
  distribution, feasible and infeasible; exact optimum by ILP (SciPy/HiGHS) where branch and bound times out; runtime
  distributions, gap, timeout and infeasibility rates distinguished, memory.
* **Text** The greedy fallback carries no optimality guarantee.

### Major 14 — refinement (E17)
* **14a (L)** No repair / deterministic / LLM-proposed without certification / LLM-proposed with certification / oracle;
  per counterexample class: success, iterations, repeated counterexamples, new invalidity, recall change, latency, tokens,
  abstention after exhaustion; blocking clauses explained and tested for cycling.

### Major 15 — experience reuse (E21)
* **15a (C)** Wire the pattern repository into the request path (seed decomposition, always revalidate). Then reuse vs
  recomputation under changed registry, model, principal, revoked tool, changed definition hash and partial similarity,
  benefit measured after mandatory revalidation.

### Major 16 — evidence status
* **16a (C)** Evidence taxonomy Measured / Observed / Human-validated / Labelled / Simulated / Formal attached to every
  result file, table row and claim; Table 7 extended accordingly.

### Section 4 findings
* 4.1 → 8a. 4.2 → 7b (inclusion-minimality, minimum-cost optimality, functional minimality reported separately).
* 4.3 (C) Full factorial coefficient table with interaction CIs; Shapley presented as descriptive attribution.
* 4.4 → 12a and E20 on registries that exercise each cost term.
* 4.5 (C) Lineage document: frozen inputs → commit → configuration → raw records → aggregates → tables/figures →
  manuscript number, one row per number of Section 8; `check_numbers_final.py` described as a numeric match check only.

### Section 7.3 — dataset separation
* (C) Report E14, E17, E18, E20 on the 95 test tasks (A1); document tool- and server-level overlap between dev, the
  300-query sample, COLT training queries and LiveMCPBench; add a tool-disjoint generalisation split to E8.

## 3. Order of work

| Phase | Content | Where | Compute (2 vCPUs) |
|---|---|---|---|
| 0 | Claim scoping and evidence taxonomy in Section 8 and in replacement text for abstract, introduction, contributions, Sections 5–7, conclusion; remove A6 and F4; Property 1 assumption | text | — |
| 1 | Validity repairs: A1, 1a, 1d, 8a, 8b, 9.1–9.5, 7a–7b, 4.3, 16a, lineage | C | ~2 h of runs |
| 2 | Retrieval: E8-R (3a), fair baselines (5a–5c), PaMCP-v2 chosen on dev and tested once (3b), frontier (6a) | C | ~3–4 h |
| 3 | Engine and operations: pair relation (10a–10b), QoS (12a), optimality (13a), experience reuse (15a) | C | ~3 h |
| 4 | Amended preregistration fixed, then LLM-dependent runs: calibration (11a), LLM repair (14a), re-typing poisoned tools (8b), third labelling (4c) | L | LLM-bound |
| 5 | Execution: observed effects (1b), attack suite (8c), end-to-end benchmark (2a), evaluator vs traces (7c) | X + L | largest effort |
| 6 | Authors: human annotation (4a, then 4b), faithful baselines on GPU (5d), other providers (11b), credentialed servers (2b) | A | — |
| 7 | Rewrite Section 8 by hypothesis and evidence category; answers to Q1–Q12; update notebook | text | — |

Decision points: after Phase 2, whether PaMCP-v2 replaces the current retrieval in the paper (decided on dev results
only); before Phase 4, the amended confirmatory family is committed; after Phase 5, whether the executed benchmark is
large enough to support claims or is reported as a feasibility study.

## 4. Draft answers to the reviewer's questions (to be completed with the results)

| Q | Answer now | Work |
|---|---|---|
| Q1 | None independent yet; zero exposure at FAR 0 follows from $U_B \subseteq U_A$ | 1a, 1b, 4a |
| Q2 | E13 needs executed servers; a local executable benchmark is added | 2a |
| Q3 | Structural score promotes type-compatible wrong tools when goal and tool typings disagree (only 50.3% of gold tools are compatible) | 3a, 3b |
| Q4 | None beyond LLM agreement | 4a, 1b |
| Q5 | They are controlled adaptations; faithful reproductions added as a second family | 5a–5d |
| Q6 | Mostly compatibility between coarse labels | 7a–7c |
| Q7 | It cannot be claimed on these registries; QoS experiment added | 12a |
| Q8 | No, as implemented; lazy and partitioned variants added | 10a |
| Q9 | It does not generalise yet; calibration suite added | 11a |
| Q10 | Deterministic operators only; LLM repair and reuse added | 14a, 15a |
| Q11 | Attacks were effect classes; scoped attacks added | 8a |
| Q12 | Not established by F3; frontier and execution results decide | 6a, 2a |

## 5. Risks

* Results may change direction (for example PaMCP-v2 may not recover retrieval); the paper is then repositioned as the
  reviewer suggests, around pre-execution certification and its evidence assumptions.
* LLM-based phases inherit the version-string limitation; record the model alias and date with every output.
* The executed benchmark will be small; it is evidence of feasibility, not of performance at scale.
* Human annotation is on the critical path for Q1 and Q4.
