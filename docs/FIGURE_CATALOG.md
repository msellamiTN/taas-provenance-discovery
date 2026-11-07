# PaMCP E1-E22 Figure Catalogue

**Figure contracts:** 80 across 22 experiments.

Each entry specifies the chart family, X/Y axes, comparison set and interpretation. The machine-readable registry is `docs/experiment_design/pamcp_plot_plan_v1.json`.

**Comparison convention:** Full PaMCP is primary where a system comparison applies. Baseline IDs are restricted to those assigned in the frozen protocol. E18 includes all eight G×P×S cells.

**Stratification:** benchmark and metric facets are mandatory wherever specified. Heterogeneous benchmarks and threat tracks are not pooled.

## E1 — Registry characterization

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E1-F1: Registry composition by source | `grouped_bar` | Tool category | Number of tools | — | Descriptive registry characterization. Compare source and merged registries; descriptive characterization, not a superiority test. |
| E1-F2: Metadata availability by server | `heatmap` | Metadata field | Server | — | Descriptive registry characterization. Compare metadata coverage across servers using consistent denominators. |
| E1-F3: Annotation and effect composition | `stacked_bar` | Registry | Tools (%) | — | Descriptive registry characterization. Compare annotation/effect categories across source registries. |

## E2 — Semantic typing quality

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E2-F1: Semantic typing confusion matrix | `confusion_matrix` | Predicted semantic type | Reference semantic type | — | Full PaMCP vs typing_structural, typing_schema_lexical. Compare structural, schema+lexical and LLM-assisted predictions in separate method facets. |
| E2-F2: Typing performance with uncertainty | `horizontal_forest` | Score | Typing method | — | Full PaMCP vs typing_structural, typing_schema_lexical. Compare typing methods; series identifies precision, recall and macro-F1. |
| E2-F3: Typing threshold trade-off | `dose_response` | Confidence threshold | Macro-F1 | — | Full PaMCP vs typing_structural, typing_schema_lexical. Compare methods over confidence thresholds; coverage belongs in a separate panel. |

## E3 — Declared versus observed effects

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E3-F1: Effect inference confusion matrix | `confusion_matrix` | Predicted effect | Observed/reference effect | — | Full PaMCP vs effects_declared, effects_lexical, effects_probe. Compare declared, lexical and probe-derived predictions in separate method facets. |
| E3-F2: Effect discrepancy by inference method | `grouped_dot` | Discrepancy rate | Effect inference method | — | Full PaMCP vs effects_declared, effects_lexical, effects_probe. Compare declared, lexical and observed/probe sources; series identifies effect class. |
| E3-F3: Probe budget versus coverage | `dose_response` | Probe budget (calls) | Probe coverage (%) | — | Full PaMCP vs effects_declared, effects_lexical, effects_probe. Compare effect-probing coverage at predeclared budgets. |

## E4 — Exposure under policy encodings

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E4-F1: Security–utility Pareto frontier | `pareto_scatter` | Util@5 | Exp@5 | benchmark | Full PaMCP vs all_tools, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare Full PaMCP provenance-aware eligibility with all policy controls assigned to E4. |
| E4-F2: Exposure before and after policy filtering | `dumbbell` | Exposure before / after policy | Policy method | — | Full PaMCP vs all_tools, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare each assigned policy against the unfiltered exposure reference. |
| E4-F3: Eligibility and utility profile | `grouped_dot` | Rate | Policy method | benchmark × metric | Full PaMCP vs all_tools, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare eligible share, Exp@5 and Util@5 in separate metric facets. |

## E5 — Forged and laundered metadata

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E5-F1: Exposure under malicious-provider fraction | `dose_response` | Malicious-provider fraction (α) | Exp@5 | benchmark | Full PaMCP vs all_tools, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare assigned policy controls over identical attack fractions. |
| E5-F2: Exposure increase relative to clean metadata | `horizontal_forest` | Change in Exp@5 | Policy method | benchmark | Full PaMCP vs all_tools, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare change from clean to forged metadata; positive values indicate increased exposure. |
| E5-F3: Utility retention under forgery | `pareto_scatter` | Util@5 | Exp@5 | benchmark | Full PaMCP vs all_tools, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare methods; facet by malicious-provider fraction. |

## E6 — Imperfect verifier

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E6-F1: Exposure as verifier FAR increases | `dose_response` | Verifier false-accept rate (FAR) | Exp@5 | benchmark | Full PaMCP vs mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare evidence eligibility with assigned policy controls over the frozen FAR grid. |
| E6-F2: Break-even false-accept rate | `horizontal_forest` | Break-even FAR | Policy comparator | benchmark | Full PaMCP vs mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare preregistered break-even FAR against assigned policy comparators. |
| E6-F3: Utility retention versus verifier errors | `dose_response` | Verifier false-accept rate (FAR) | Util@5 | benchmark | Full PaMCP vs mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare utility retention using the same FAR grid as E6-F1. |

## E7 — Trust policy and evidence strength

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E7-F1: Evidence threshold security–utility frontier | `pareto_scatter` | Util@5 | Exp@5 | benchmark | Full PaMCP vs mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare evidence thresholds and assigned policy controls. |
| E7-F2: Eligible share across trust thresholds | `heatmap` | Minimum evidence threshold | Effect/property class | benchmark | Full PaMCP vs mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Show eligible share for each property-specific evidence threshold. |
| E7-F3: Policy encoding outcome matrix | `heatmap` | Policy encoding | Outcome metric | benchmark | Full PaMCP vs mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence. Compare eligible share, Exp@5 and Util@5 separately. |

## E8 — Single-tool retrieval quality

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E8-F1: Single-tool retrieval performance | `horizontal_forest` | Retrieval score | Method | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted. Compare Full PaMCP with E8-assigned retrieval baselines; series identifies Hit@1, Hit@5 and MRR@10. |
| E8-F2: B1 versus B1m retrieval comparison | `grouped_bar` | Retrieval method | Macro Hit@1 | — | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted. Compare B1 and B1m under identical MCPToolBench++ task definitions. |
| E8-F3: Retrieval robustness to distractors | `scatter` | Number of distractor tools | Hit@1 | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted. Compare PaMCP and retrieval baselines at matched candidate budgets. |
| E8-F4: Cross-benchmark retrieval diagnostics | `horizontal_forest` | Retrieval score | Method | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted. Compare methods separately by benchmark; do not pool heterogeneous ToolRet with MCP-native results. |

## E9 — Multi-tool set retrieval

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E9-F1: Goal-group retrieval recall | `grouped_dot` | Group recall@k | Method | benchmark | Full PaMCP vs rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, all_tools. Compare Full PaMCP with E9-assigned retrieval/planning baselines; series identifies benchmark or k. |
| E9-F2: Set precision versus group recall | `pareto_scatter` | Set precision | Group recall@k | benchmark | Full PaMCP vs rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, all_tools. Compare complete-set quality and recall; bubble size is complete-set share. |
| E9-F3: Complete-set coverage by task group | `heatmap` | Task group | Method | benchmark | Full PaMCP vs rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, all_tools. Compare methods by task group; separate MCP-Atlas trajectory diagnostics. |

## E10 — Set validity and compatibility

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E10-F1: Joint feasibility across methods | `horizontal_forest` | Joint-feasibility rate | Method | benchmark | Full PaMCP vs mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, fides_ifc, camel_ifc, all_tools. Compare Full PaMCP with assigned discovery methods and separately identified IFC comparators. |
| E10-F2: Certificate checks by method | `heatmap` | Certificate check | Method | benchmark | Full PaMCP vs mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, fides_ifc, camel_ifc, all_tools. Show S, C, P, E, L and V; baseline sets are independently evaluated counterfactuals. |
| E10-F3: Invalid-set failure composition | `stacked_horizontal` | Invalid sets (%) | Method | benchmark | Full PaMCP vs mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, fides_ifc, camel_ifc, all_tools. Compare interface, forbidden-pair, effect, flow and other failure causes. |

## E11 — Capability gap and bridge ratio

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E11-F1: Toolkit size as task input grows | `line` | Task input size (n) | Toolkit size | — | Full PaMCP vs mcp_zero, per_subtask, cmtf_adapted, uncalibrated_profile, calibrated_profile. Compare Full PaMCP, MCP-Zero, per-subtask and CMTF under matched task settings. |
| E11-F2: Bridge ratio under model profiles | `line` | Task input size (n) | Bridge ratio | — | Full PaMCP vs mcp_zero, per_subtask, cmtf_adapted, uncalibrated_profile, calibrated_profile. Compare calibrated and uncalibrated profiles using the paper's formal bridge-ratio definition. |
| E11-F3: Toolkit size versus model reliability | `interaction_plot` | Model reliability threshold (τ) | Toolkit size | — | Full PaMCP vs mcp_zero, per_subtask, cmtf_adapted, uncalibrated_profile, calibrated_profile. Compare conditional toolkit sizes across model-profile conditions. |
| E11-F4: Native capability versus task success | `pareto_scatter` | Native-goal share | Task success | — | Full PaMCP vs mcp_zero, per_subtask, cmtf_adapted, uncalibrated_profile, calibrated_profile. Compare calibrated and uncalibrated profiles; task success must be externally evaluated. |

## E12 — Model profile calibration

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E12-F1: Measured reliability by class and input size | `heatmap` | Input size (n) | Model capability class | model | Full PaMCP vs self_assessed_profile, uncalibrated_profile, calibrated_profile. Display measured reliability with separate model facets. |
| E12-F2: Claimed versus measured reliability | `calibration_scatter` | Claimed reliability | Measured reliability | — | Full PaMCP vs self_assessed_profile, uncalibrated_profile, calibrated_profile. Compare self-assessment with empirical reliability and include the identity line. |
| E12-F3: Calibrated reliability estimates | `horizontal_forest` | Measured reliability ρ | Model / capability class | — | Full PaMCP vs self_assessed_profile, uncalibrated_profile, calibrated_profile. Compare self-assessed, uncalibrated and calibrated profiles. |
| E12-F4: Capability refutation rate | `grouped_dot` | Refutation rate | Model profile | — | Full PaMCP vs self_assessed_profile, uncalibrated_profile, calibrated_profile. Compare refutation rates by capability class and profile. |

## E13 — End-to-end agent execution

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E13-F1: End-to-end task success | `horizontal_forest` | Task-success rate | Method | benchmark | Full PaMCP vs all_tools, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Compare Full PaMCP with E13-assigned discovery and runtime-security methods. |
| E13-F2: Task success versus token cost | `pareto_scatter` | Tokens per task | Task success | benchmark | Full PaMCP vs all_tools, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Compare task utility and interaction cost using a frozen tokenizer. |
| E13-F3: Execution-step distribution | `violin` | Method | Execution steps per task | benchmark | Full PaMCP vs all_tools, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Compare task-level execution-step distributions; retain individual task observations. |
| E13-F4: Wrong-tool call composition | `stacked_horizontal` | Wrong-tool calls | Method | benchmark | Full PaMCP vs all_tools, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Separate irrelevant, invalid-state and policy-violating calls. |
| E13-F5: Paired task-success differences | `horizontal_forest` | PaMCP minus baseline task success | Baseline comparator | benchmark | Full PaMCP vs all_tools, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Show paired task effects; positive values indicate PaMCP improvement. |

## E14 — Robustness under prompt injection

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E14-F1: Security–utility frontier under injection | `pareto_scatter` | Executed out-of-policy actions per task | Task success | benchmark × attack_type | Full PaMCP vs all_tools, rag_mcp, mcp_zero, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Compare PaMCP with assigned discovery/runtime-security baselines under identical attacks. |
| E14-F2: Executed violations by attack family | `heatmap` | System | Attack family | benchmark | Full PaMCP vs all_tools, rag_mcp, mcp_zero, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Keep MCPTox, InjecAgent and controlled MCP injection as separate attack tracks. |
| E14-F3: Attack-induced task-success change | `horizontal_forest` | Change in task-success rate | Method | benchmark × attack_type | Full PaMCP vs all_tools, rag_mcp, mcp_zero, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Compare attack degradation against matched clean conditions. |
| E14-F4: Unsafe retrieval exposure by attack | `grouped_dot` | Exp@5 | System | benchmark × attack_type | Full PaMCP vs all_tools, rag_mcp, mcp_zero, toolscope_adapted, cmtf_adapted, progent_runtime, fides_ifc, camel_ifc. Compare exposure by attack family; R-Judge remains a separate risk-awareness diagnostic. |

## E15 — Cost per request and scalability

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E15-F1: Latency scaling by registry size | `loglog_scaling` | Registry size (tools) | Latency (ms) | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, colt_adapted, toolscope_adapted, cmtf_adapted, linear_scan. Compare PaMCP and assigned retrieval/planning systems; p50 and p95 are separate series. |
| E15-F2: Latency percentiles by method | `grouped_dot` | Latency (ms) | Method | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, colt_adapted, toolscope_adapted, cmtf_adapted, linear_scan. Compare p50 and p95 at matched registry sizes; facet by registry size. |
| E15-F3: Memory versus p95 latency | `pareto_scatter` | Peak memory (MB) | p95 latency (ms) | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, colt_adapted, toolscope_adapted, cmtf_adapted, linear_scan. Compare systems under identical registry snapshots and workloads. |
| E15-F4: Exact versus greedy composition gap | `line` | Problem size | Optimality gap (%) | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, colt_adapted, toolscope_adapted, cmtf_adapted, linear_scan. Compare exact and greedy PaMCP composition; report runtime separately. |

## E16 — Registry and model evolution

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E16-F1: Incremental update versus full rebuild | `dumbbell` | Update time (ms) | Mutation / event class | benchmark | Full PaMCP vs full_rebuild. Compare incremental maintenance and full rebuild per mutation/event class. |
| E16-F2: Update latency over event sequence | `scatter` | Registry event index | Update latency (ms) | benchmark | Full PaMCP vs full_rebuild. Compare incremental maintenance and recomputation over identical event sequences. |
| E16-F3: Correctness against recomputation | `heatmap` | Mutation type | Correctness property | benchmark | Full PaMCP vs full_rebuild. Compare incremental state with recomputation for invalidation, eligibility and evidence correctness. |
| E16-F4: Evidence lifecycle through registry changes | `alluvial` | Evidence state before mutation | Evidence state after mutation | benchmark | Full PaMCP vs full_rebuild. Show changed, retained, invalidated and stale evidence transitions from observed records. |

## E17 — Counterexample-guided refinement

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E17-F1: Counterexample-to-outcome flow | `alluvial` | Counterexample category | Repair outcome | — | Full PaMCP vs no_refinement. Compare outcomes by χ category, including repaired, abstained and unresolved cases. |
| E17-F2: Repair success by counterexample type | `grouped_dot` | Repair-success rate | Counterexample type (χ) | — | Full PaMCP vs no_refinement. Compare Full PaMCP refinement against the no-refinement control. |
| E17-F3: Cumulative repair success by iteration | `line` | Refinement iteration | Cumulative repair success | — | Full PaMCP vs no_refinement. Compare Full PaMCP and no-refinement; keep failed/abstained tasks in denominator. |
| E17-F4: Repair success versus token cost | `pareto_scatter` | Tokens consumed | Repair success | — | Full PaMCP vs no_refinement. Compare refinement configurations and no-refinement control. |

## E18 — Component and primary mechanism ablation

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E18-F1: Complete eight-cell factorial outcome matrix | `factorial_heatmap` | Outcome metric | G-P-S configuration | benchmark × metric | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence, no_refinement. Show all eight frozen G×P×S cells; use a separate panel per outcome metric. |
| E18-F2: Factor main effects and interactions | `horizontal_forest` | Estimated factorial effect | Factor / interaction | benchmark × metric | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence, no_refinement. Estimate G, P, S, G×P, G×S, P×S and G×P×S from all eight cells. |
| E18-F3: Mechanism interaction plot | `interaction_plot` | Factor level | Outcome | benchmark × metric | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence, no_refinement. Plot conditional means across levels of a second factor; generate per interaction and outcome. |
| E18-F4: Leave-one-out paired contrasts | `horizontal_forest` | Full PaMCP minus ablation | Ablation | benchmark × metric | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence, no_refinement. Compare Full PaMCP with NoGap, Declared and NoCert on matched tasks. |
| E18-F5: Factorial security–utility trade-off | `pareto_scatter` | Exp@5 | Task success | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, mcp_default_annotations, closed_world_annotations, lexical_positive, lexical_closed_world, verified_evidence, no_refinement. Compare all eight factorial configurations and assigned external controls. |

## E19 — LLM role configurations

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E19-F1: LLM role configuration outcome matrix | `heatmap` | Outcome metric | LLM/profile configuration | metric | Full PaMCP vs self_assessed_profile, uncalibrated_profile, calibrated_profile. Compare GoalSpec validity, repair, task success, tokens and latency in separate metric facets. |
| E19-F2: GoalSpec and execution quality by role | `grouped_dot` | Performance | LLM role configuration | — | Full PaMCP vs self_assessed_profile, uncalibrated_profile, calibrated_profile. Compare profile/analyst role configurations; series identifies validity, repair and task-success metrics. |
| E19-F3: Quality versus token cost | `pareto_scatter` | Tokens per task | Task success | — | Full PaMCP vs self_assessed_profile, uncalibrated_profile, calibrated_profile. Compare role configurations; latency is reported separately. |

## E20 — Sensitivity to cost and utility weights

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E20-F1: Task-success weight-space heatmap | `heatmap` | Cost weight | Utility weight | benchmark | Full PaMCP vs calibrated_profile. Show task success for every evaluated parameter pair. |
| E20-F2: Toolkit stability and security sensitivity | `heatmap` | Cost weight | Utility weight | benchmark | Full PaMCP vs calibrated_profile. Use separate panels for toolkit Jaccard and Exp@5; do not aggregate them. |
| E20-F3: Price–latency Pareto surface | `pareto_scatter` | Price per task | Latency per task | benchmark | Full PaMCP vs calibrated_profile. Compare frozen weight settings; task success is an annotation, not a composite score. |
| E20-F4: Selected-toolkit similarity matrix | `heatmap` | Weight configuration A | Weight configuration B | benchmark | Full PaMCP vs calibrated_profile. Compare pairwise toolkit Jaccard similarity across evaluated weight configurations. |

## E21 — Experience reuse

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E21-F1: Trajectory reuse versus repository size | `line` | Confirmed trajectories in repository | Reuse rate | benchmark | Full PaMCP vs autotool_adapted, no_experience. Compare AutoTool trajectory reuse against no-experience control. |
| E21-F2: Latency savings versus repository size | `line` | Confirmed trajectories in repository | Latency saved (ms) | benchmark | Full PaMCP vs autotool_adapted, no_experience. Compare experience reuse with no-experience retrieval. |
| E21-F3: Stale-trajectory detection matrix | `confusion_matrix` | Predicted trajectory status | Reference trajectory status | benchmark | Full PaMCP vs autotool_adapted, no_experience. Evaluate stale and valid trajectory detection against independently confirmed status. |
| E21-F4: Reuse savings and repository cost | `pareto_scatter` | Repository size | Latency saved (ms) | benchmark | Full PaMCP vs autotool_adapted, no_experience. Compare repository configurations; bubble size represents reuse rate. |

## E22 — Statistical validity and reproducibility

| Figure | Chart | X-axis | Y-axis | Facets | Comparison / interpretation |
|---|---|---|---|---|---|
| E22-F1: Paired PaMCP-versus-baseline effect sizes | `horizontal_forest` | PaMCP minus baseline effect | Baseline comparator | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, colt_adapted, toolscope_adapted, cmtf_adapted, per_subtask. Show paired effects for E22-assigned methods; define beneficial direction per metric. |
| E22-F2: Confidence-interval width by method and metric | `grouped_dot` | 95% CI width | Method | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, colt_adapted, toolscope_adapted, cmtf_adapted, per_subtask. Compare interval widths by metric and method; report the resampling unit. |
| E22-F3: Method rank probability | `rankogram` | Rank | Probability of rank | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, colt_adapted, toolscope_adapted, cmtf_adapted, per_subtask. Compare rank distributions over valid tool-disjoint resamples. |
| E22-F4: Effect size versus adjusted significance | `significance_scatter` | Paired effect size | Holm/BH adjusted p-value | benchmark | Full PaMCP vs bm25, dense_lsa, rag_mcp, mcp_zero, colt_adapted, toolscope_adapted, cmtf_adapted, per_subtask. Separate confirmatory Holm and designated exploratory BH families. |

## Output conventions

One normalized CSV is expected per figure under `results/visualization/data/`. Rendered outputs are PDF, SVG and PNG under `results/visualization/figures/`. Forest plots require bootstrap confidence intervals. Matched-task effects preserve pairing. All figures must include exact denominators/sample sizes where applicable.
