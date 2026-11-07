# PaMCP Core Experimental Protocol v2.0

**Status:** preregistration and execution contract. This document defines the experiment; it does not assert that all experiments have run.

## 1. Research question

Does PaMCP Core improve evidence-grounded tool discovery and set-level assurance over retrieval-only, model-driven, composition, policy-only, and experience-reuse baselines, while controlling execution risk and resource cost?

The unit of evaluation is a task/request under a frozen registry snapshot and visibility set. The discovery process must never access evaluator-only references.

## 2. PaMCP Core feature model

| Core feature | Operational definition | Evidence required | Experiments |
|---|---|---|---|
| Objective engineering / GoalSpec | Convert user objective into typed goals, constraints and required outputs | Frozen objective + independently annotated GoalSpec | E11, E12, E19 |
| Capability discovery | Retrieve candidate tools from the visible registry | Complete candidate corpus + relevance qrels | E8, E9 |
| Capability typing/contracts | Map tool input/output semantics to typed capability contracts | Double-annotated tool definitions and adjudication | E2, E10 |
| Provenance/evidence | Track source, version, definition hash, evidence class and trust | Independent provenance records | E4-E7 |
| Gap analysis | Identify required capabilities not covered by eligible tools | Independent required-capability oracle | E11 |
| Composition/assurance | Select a jointly feasible set satisfying dependency, type, policy and effect constraints | Independent composition oracle | E10, E18 |
| Policy/security | Enforce allow/deny, trust, information-flow and adversarial constraints | Independent policy labels and sandbox outcomes | E4-E7, E14 |
| Counterexample refinement | Revise a proposal after independently verified counterexamples | Valid/invalid composition pairs | E17 |
| Experience reuse | Reuse validated trajectories without test leakage | Train-only trajectories + held-out tasks | E21 |
| Calibration/roles | Calibrate model confidence and role-specific decisions | Independent calibration labels, same task budget | E12, E19, E20 |
| Evolution/scalability | Update indexes and evidence under registry growth/change | Versioned snapshots and controlled expansions | E15, E16 |

## 3. Dataset portfolio and track separation

| Dataset | Track / experiments | Permitted evidence | Explicit limitation |
|---|---|---|---|
| ToolRet | Retrieval E8 | Full corpus, queries, graded qrels | Not MCP execution, safety or provenance oracle |
| LiveMCPBench | Discovery E9, registry characterization | Task and tool catalogue, source trajectories if released | Validate exact release and acceptable-set semantics |
| MCP-Atlas public | Multi-tool discovery/composition E9/E10; execution only where runnable | Per-task ENABLED_TOOLS visibility; GTFA claims; diagnostic trajectories | Public 500-task release; trajectory is not exhaustive acceptable-set gold |
| MCPToolBench++ | Registry/retrieval/scale E1/E8/E9/E15 | Exact acquired subset and source metadata | Report 87 tools/10 servers in current repo separately from >4,000-server dataset-card claim; no population equivalence |
| MCPVerse v1.1 | Registry/evolution E1/E15/E16 | Pinned time-invariant task CSV and tool labels | Not a complete executable tool-schema corpus |
| DynamicMCPBench | Effects/composition E3/E10/E13 | Only released effect checkpoints and successful traces, verified against source | Do not assume effect labels transfer to unrelated servers |
| Toolathlon-Verified | Execution E13, refinement E17, trajectories E21 | Native evaluator and verified tasks | Pin release/evaluator; check redistribution and runtime |
| MCP-Universe | Execution E13 | Native task/environment evaluator | Requires runtime availability |
| τ-bench / τ³-bench | Stateful task and policy E10/E13/E14 | Final-state evaluator and policy scenarios | Not tool discovery ground truth |
| BFCL V4 | Interface/function-call correctness | Native function-call evaluator | Not provenance or operational-effect ground truth |
| MCPTox | Tool-description poisoning E14 | Attack cases and source labels | Not observed operational effects |
| InjecAgent | Indirect injection E14 | Attack cases and risk labels | Not MCP registry poisoning |
| R-Judge | Risk judgement E14 | Human risk annotations | License/use restrictions; check CC BY-NC-SA terms |
| Independent PaMCP oracle corpus | E2/E3/E10/E11/E14/E17 | Human adjudication, isolated probes, state snapshots | Must be created independently of PaMCP predictions |

Never pool all datasets into one leaderboard. Report per-dataset and per-track metrics; aggregate only on a declared common task intersection with compatible label semantics.

## 4. Baseline protocol

| Baseline | Track | Fidelity and requirements |
|---|---|---|
| Random | E8/E9 | Deterministic seeded ranking |
| BM25 | E8/E9/E15 | Existing ToolRet outputs reused if manifest and hashes match |
| TF-IDF | E8/E9/E15 | Existing ToolRet outputs reused if manifest and hashes match |
| Dense E5/BGE | E8/E9 | Pin model and tokenizer; no test-qrel tuning |
| Hybrid BM25+dense | E8/E9 | Tune fusion only on development split |
| Cross-encoder reranker | E8/E9 | Candidate pool and reranker frozen before test |
| MCP-Zero | E8/E9; E13 only if runnable | Native iterative active request method distinguished from single-pass adaptation |
| COLT | E9 | Train scenes from training query-tool bundles only; server co-membership is not a task scene |
| ToolScope | E8/E9 | Separate no-merge, merge, and no-correction variants; preserve original tool identities and evidence |
| LLM selection / ReAct / native MCP client | E9/E10/E13/E14 | Same model, prompts, visible tools, budgets, sandbox and evaluator |
| CMTF | E10/E13 | Shared-contract and independently annotated-contract conditions |
| Policy-only | E4-E7/E14 | Deterministic allow/deny baseline, no PaMCP provenance or joint assurance |
| AutoTool | E21 only | Transition graph from training trajectories only; held-out tasks for test |

Every result must be tagged native_reproduction, faithful_reproduction, adaptation, surrogate, or partial. Do not call a clean-room COLT-style or single-pass MCP-Zero adapter an exact reproduction.

## 5. Ablations and factorial design

Use all eight G/P/S cells. G = model-conditioned capability-gap analysis; P = provenance-sound eligibility; S = joint set-level reasoning and assurance. S is not merely certificate formatting: it includes joint selection, dependencies, compatibility, effects and policy checks.

| Cell | G | P | S |
|---|---:|---:|---:|
| Full PaMCP | 1 | 1 | 1 |
| G1_P1_S0 | 1 | 1 | 0 |
| G1_P0_S1 | 1 | 0 | 1 |
| G1_P0_S0 | 1 | 0 | 0 |
| G0_P1_S1 | 0 | 1 | 1 |
| G0_P1_S0 | 0 | 1 | 0 |
| G0_P0_S1 | 0 | 0 | 1 |
| G0_P0_S0 | 0 | 0 | 0 |

All eight must be genuine code-level interventions. Keep the same task, candidate visibility, model profile, budgets and oracle. Estimate factorial main effects and interactions; report conditional leave-one-factor-out contrasts without assuming additivity.

Additional one-factor ablations: semantic typing, effect evidence, refinement, calibration, role specialization, and experience reuse. Do not conflate these with G/P/S.

## 6. Metrics and contracts

- Retrieval: Precision@k, Recall@k, MRR, nDCG@k, Hit@k.
- Multi-tool: complete-set recall / COMP@k, group recall, exact-set match. On single-gold tasks COMP@k reduces to Hit@k; report multi-tool subset separately.
- Typing: macro/micro precision, recall, F1, confusion matrix, Cohen's kappa.
- Effects: observed-effect precision/recall/F1, probe coverage, declared-vs-observed discrepancy. Unknown is not negative.
- Provenance: completeness, source traceability, hash/version integrity, unsupported-evidence rate.
- Composition: independent valid-composition rate, constraint/dependency violations, unsupported transitions.
- Gap analysis: gap precision/recall/F1, correct abstention, coverage.
- Calibration: Brier score, ECE, reliability diagram, selective risk.
- Execution: task success and final-state correctness from native/independent evaluator; wrong-tool calls, premature actions.
- Security: attack success rate, attempted unsafe actions, executed out-of-policy actions, false refusal.
- Exposure@k = mean over requests of indicator that top-k contains at least one independently labelled unsafe tool.
- UnsafeShare@k = total unsafe tools in top-k divided by total returned tools. Keep distinct.
- Efficiency: latency, tokens, model calls, tool calls, memory and compute.
- Evolution: stale-result rate, update latency, quality degradation after registry change.
- Refinement: counterexample correction rate and regression rate.
- Experience: held-out reuse success, tokens saved, error propagation.

For Util@5, preregister denominator, eligible target definition, alternatives and abstentions. Report unconditional utility and coverage; do not hide abstentions by conditioning silently.

## 7. Data governance and leakage prevention

Every record preserves dataset_id, dataset_version, source_revision, license, task_id, source_tool_id, canonical_tool_id, server_id, definition_hash, split, reference_source, reference_confidence, execution_available and provenance.

- Keep discovery/ and evaluator/ physically separated.
- Do not expose qrels, oracle labels, attack labels, GTFA claims or test trajectories to discovery-time code.
- Train COLT scenes and AutoTool transition graphs on training data only.
- Deduplicate tasks by exact and near-duplicate checks across sources; report overlaps.
- Tool/server-disjoint and task-disjoint splits for generalization; version-disjoint for evolution.
- No credential-bearing live probes. Use isolated, least-privilege sandboxes.
- Preserve licenses and source attribution. Do not redistribute restricted datasets or raw records without permission.

## 8. Statistical protocol

Use paired task-level comparisons on common tasks; bootstrap by task and cluster by server where appropriate. Report N, denominator, exclusions, abstentions, point estimate, 95% CI, paired effect size, adjusted p-value, seeds and artifact hashes. Use paired sign-flip/permutation tests for matched outcomes; Holm correction for preregistered confirmatory family; BH only for declared exploratory family. Seeds are not independent task observations.

## 9. Experiment execution status

Statuses: EXECUTED, READY_LOCAL, BLOCKED_ORACLE, BLOCKED_EXECUTION, BLOCKED_LICENSE, BLOCKED_DATA, NOT_APPLICABLE. A software test is not a scientific experiment. A dataset adapter is not evidence of benchmark execution. Never impute missing oracle labels or synthesize scores.

Initial realistic readiness:
- E1: runnable descriptively; inferential semantic/effect claims require independent labels.
- E2: BLOCKED_ORACLE until human annotation/adjudication exists.
- E3: BLOCKED_ORACLE/BLOCKED_EXECUTION until isolated observed-effect traces and adjudicated references exist.
- E8: READY_LOCAL for ToolRet using complete corpus and pinned qrels; reuse prior results only after manifest/hash validation.
- E9: dataset-specific; MCP-Atlas trajectories alone do not provide exhaustive acceptable tool sets.
- E10/E13: BLOCKED_EXECUTION/ORACLE until executable tasks and independent composition/final-state evaluators are wired.
- E14: READY only for released offline attack labels; execution claims require sandbox.
- E15/E16: require controlled synthetic expansion/versioned snapshots; report synthetic separately.
- E21: BLOCKED_DATA until eligible train/test trajectories are acquired and split.
- E22: runs across confirmatory experiments; not a standalone dataset score.

## 10. Colab execution contract

The one-shot Colab notebook must:
1. Fetch the exact branch commit robustly (remote-tracking ref + reset; no fragile FETCH_HEAD checkout assumptions).
2. Install pinned project extras and run protocol tests.
3. Validate source revisions, licenses, archive hashes and manifests.
4. Reuse ToolRet cached rankings only when dataset revisions, corpus/query hashes, adapter version, parameters and metric contract match.
5. Acquire/adapt each dataset through source-specific adapters; never infer source schema or silently substitute.
6. Execute compatible baselines and PaMCP variants with discovery/evaluator separation.
7. Record blocked reasons for unavailable oracles, runtimes or licenses.
8. Produce raw per-task predictions, metrics, paired CIs/tests, plots, run manifest and ZIP.
9. Be restart-safe and skip valid cached outputs; never silently overwrite a prior run.
10. Print a final matrix of executed/blocked/not-applicable experiments.

The notebook must not claim Colab has run until the user actually executes it. No superiority claims before independent oracle-backed runs.
