# PaMCP E1–E22 Offline Evaluation Implementation Matrix

**Protocol:** `pamcp_experiments_v1.json` v1.0.0  
**Baselines:** `pamcp_baselines_v1.json` v1.0.0  
**Execution policy:** evaluation toolkit only. No MCP calls, server launches, or tool execution.

This matrix records evaluator coverage, not experimental completion. Canonical experiment statuses
remain `planned_not_run`. The workbench must not change those statuses merely because an evaluator
or test has been committed.

| Experiment | Offline evaluator implementation | Required evidence / current limitation |
|---|---|---|
| E1 Registry characterization | `registry_typing_evaluators.registry_characterization` | Frozen registry snapshot |
| E2 Semantic typing quality | `semantic_typing_metrics`, `typing_threshold_curve` | Independent human reference labels; missing labels block empirical scores |
| E3 Declared vs observed effects | `provenance_policy_evaluators.effect_discrepancy`, `probe_coverage` | Hash-bound independent observed-effect records |
| E4 Policy exposure | `policy_encoding_metrics` | Rankings, independent unsafe labels, read-only qrels, per-encoding eligibility |
| E5 Forged/laundered metadata | `malicious_provider_exposure_curve` | Explicit malicious-provider assignments and provider mapping |
| E6 Imperfect verifier | `verifier_error_rates`, `verifier_threshold_sweep` | Independent labels and actual frozen verifier scores; FAR = unsafe accepted as safe |
| E7 Trust/evidence strength | `trust_threshold_sweep`, `policy_threshold_pareto` | Frozen provenance strengths and policy results |
| E8 Single-tool retrieval | `evaluation_metrics.retrieval_metrics` | Frozen B1/B1m rankings and qrels; baseline adapters separately identified |
| E9 Multi-tool retrieval | `evaluation_metrics.multi_tool_set_metrics` | LiveMCPBench acceptable goal groups and rankings |
| E10 Set validity/certification | `independent_certificate_audit.audit_certificate`, `certificate_check_metrics` | Frozen graph, goals, policy, model profile and independent audit inputs |
| E11 Capability gap/bridge ratio | `gap_execution_factorial_evaluators.capability_gap_metrics` | Frozen review tasks and calibrated model profile; exact Definition 3 bridge ratio |
| E12 Model profile calibration | `calibration_refinement_roles_experience.model_profile_calibration` | Purpose-built frozen calibration set; external calibration-set freeze |
| E13 End-to-end execution | `end_to_end_metrics` | Existing confirmed trajectories and external task oracle; no execution is initiated |
| E14 Prompt injection | `prompt_injection_metrics` | Existing injection trajectories and independent policy oracle; exposure/attempt/execution separated |
| E15 Cost/scalability | `scalability_summary`, `exact_greedy_gap` | Frozen timing/memory records and exact/greedy objective outputs |
| E16 Registry/model evolution | `evolution_replay_metrics` | Frozen event replay and full-recomputation states |
| E17 Counterexample refinement | `refinement_metrics` | Existing refinement records grouped by χ |
| E18 Component/factorial ablation | `factorial_effects` | All eight 2³ cells; three leave-one-out contrasts are not substituted for factorial effects |
| E19 LLM role configurations | `role_configuration_metrics` | Frozen role runs with GoalSpec validity, repair, task success, tokens and latency |
| E20 Cost/utility sensitivity | `weight_sensitivity` | Frozen toolkit selections per weight setting; QoS and utility inputs retain evidence class |
| E21 Experience reuse | `experience_reuse_metrics` | Confirmed execution trajectory repository; AutoTool remains E21-only |
| E22 Statistical validity | `percentile_bootstrap`, `paired_sign_flip`, `adjust_pvalues`, `rank_stability` | Paired E8–E10 outcomes and tool-disjoint split manifest |

## Important limits

1. The evaluator layer is not a replacement for the protocol's independent semantic labels,
   observed-effect probes, external task oracle, runtime security outcomes or confirmed
   trajectory repository.
2. E3, E13 and E14 cannot be made empirical from registry metadata alone. This implementation
   accepts only already available records and does not create observations.
3. E10's certificate checker recomputes S,C,P,E,L,V from frozen inputs, but shares canonical
   hypergraph/domain primitives. It is a separate certificate rechecker, not an independently
   reimplemented formal semantics.
4. The baseline catalog's maturity labels govern claims. A metric function does not establish
   that MCP-Zero, COLT, ToolScope, CMTF, Progent, Fides, CaMeL or AutoTool has been faithfully
   reproduced.
5. Statistical routines operate on the supplied resampling units. The caller must supply
   request-level or target-tool-level paired observations as prescribed by E22; rows are not
   interchangeable independent samples by default.
6. All outputs must include run ID, seed, commit, dataset snapshot, definition hashes,
   parameters, exact N/denominators, unknowns, abstentions and exclusions.

## Readiness

`protocol_readiness.assess_programme_readiness` checks the approved dependency graph,
external gates and named artifact prerequisites for all 22 experiments. It reports readiness
only; it does not execute or mutate experiment status.


## Unified dispatch

`src/taas/experiments/offline_evaluator.py::evaluate_payload(experiment_id, payload)`
provides one dispatch entry point for record-based E1–E22 analyses. It validates required
top-level payload fields and calls the experiment-specific evaluators. E10's per-certificate
recomputation remains a separate typed-object operation; the dispatcher aggregates its
independent audit records. The dispatcher does not mark experiments complete or create
missing observations.

E8 retrieval reports `MRR@max(k)`; the E8 dispatch requests k = 1, 5 and 10, therefore
the protocol output is `MRR@10`. E12 calibration gaps and refutations are computed at the
calibration-cell level (class, n, language and exactness), comparing mean claimed reliability
with measured cell accuracy.


## Offline CLI

`experiments/evaluate_offline.py` evaluates one frozen JSON payload. The input envelope
must contain `protocol_version`, `dataset_snapshot_hash`, `definition_hash_manifest`
and a `payload` object. Example:

```bash
python experiments/evaluate_offline.py \
  --experiment E8 \
  --input artifacts/e8/frozen_payload.json \
  --output artifacts/e8/evaluation.json \
  --run-id E8-run-001 \
  --seed 17
```

The output records the input SHA-256, run ID, protocol/dataset/hash metadata, seed and
an explicit `evaluated_payload_not_experiment_completion` status. The CLI is an evaluator,
not a runner for model agents or MCP tools. The output's timestamp records when the local
evaluation command was invoked.
