# Response to the TSC experimental review — Revision 1

This response distinguishes implemented analysis corrections from new empirical work that still requires data collection. “Added” means code or protocol is present in this revision directory; it does not mean the associated script has already been executed or that new experimental observations have been collected.

| Reviewer comment | Revision action | Status |
|---|---|---|
| 1. \(J_A/J_B\) containment makes simulated zero exposure dependent on label construction | Added a direct overlap audit; revised the interpretation of E4–E7 and E14; zero exposure is no longer presented as independent verifier validation | Analysis correction added; audit script pending execution |
| 2. No end-to-end execution (E13) | Defined an executable MCP benchmark with execution traces, task oracles, runtime effects and task-success metrics | Protocol added; execution pending |
| 3. Structural retrieval has poor full-registry Hit@1 | Preserved the negative result; specifies relevance-first, confidence-gated, oracle-type and human-type ablations | Claim corrected; new retrieval runs pending |
| 4. LLM-generated labels are not independent ground truth | Explicitly labels \(J_A/J_B\) as machine-generated proxies; specifies dual human annotation and adjudication | Claim corrected; human study pending |
| 5. Baseline adaptations may not represent original systems | Requires faithful/official baselines separately from controlled adaptations, with matched information and tuning budgets | Protocol added; reproduction pending |
| 6. Composition superiority is not established | Reports failed non-inferiority and non-significant joint-feasibility comparison; adds quality–risk–cost Pareto evaluation | Claim corrected; additional runs pending |
| 7. The separate E10 evaluator is not an independent oracle | Describes it as separately implemented but dependent on the same analyst goals and \(J_B\) labels; adds fail-closed scope semantics and tests | Analysis correction added; evaluator validation pending |
| 8. E14 is offline, poisoning exposure was assigned zero, and some tampering cases were skipped | Removes conditional attack omission in the new re-analysis; recomputes from actual toolkit contents; adds sanitizer canary audit and scope-aware outcomes | New re-analysis added; execution pending |
| 9. Statistical unit for E14 is task × attack | New comparison first aggregates attacks within each task, then resamples/sign-flips at task level; explicitly marks the changed F5 estimand exploratory | Analysis code added; execution pending |
| 10. Scalability uses near-duplicate clones | Limits the current claim to synthetic clone scaling and bitmap microbenchmarks; specifies heterogeneous, real-registry workloads | Claim corrected; new workloads pending |
| 11. Model profile uses only 64 items and four classes | Limits current inference to the tested classes/items; specifies a larger stratified calibration and selective-risk evaluation | Claim corrected; new calibration pending |
| 12. QoS fields are defaulted because registry QoS is absent | Removes any claim that the current experiments demonstrate QoS advantage; specifies a differentiated-QoS benchmark | Claim corrected; new benchmark pending |
| 13. Exact-versus-greedy search is constrained and times out | Limits conclusions to the generated instances and node budget; requires timeout/infeasibility distinction and varied instances | Claim corrected; expanded benchmark pending |
| 14. E17 tests deterministic repair, not LLM assistant repair | Describes E17 as deterministic repair only; specifies no-repair, deterministic, LLM-proposed, certified-LLM and oracle variants | Claim corrected; LLM repair runs pending |
| 15. E21 experience reuse not run | Removes empirical benefit claims and defines revalidation-aware reuse comparisons | Claim corrected; E21 pending |
| 16. Evidence classes are mixed throughout the manuscript | Adds an evidence ledger and revised section with explicit measured, labelled, simulated, synthetic, formal and blocked distinctions | Added |

## Responses to the twelve direct reviewer questions

1. **Independent evidence for zero unsafe exposure:** None is currently established. The committed label relationship \(U_B \subseteq U_A\) means the error-free simulated verifier cannot admit a \(J_B\)-unsafe tool. This outcome is construction-dependent. The revision withdraws the independent empirical interpretation.
2. **Why E13 was not run:** The original evaluation did not have an executable MCP server/task-oracle environment. The paper must state this as a limitation; E13 remains a prerequisite for any end-to-end claim.
3. **Why 23% Hit@1:** The existing diagnostic attributes the loss to goal/tool type disagreement and the structural rank component. The revision treats this as a negative result, not a successful retrieval result. Confidence-gated and relevance-first strategies must be evaluated before changing the algorithmic claim.
4. **Evidence for semantic contract correctness:** The current reference labels are LLM-generated; they do not establish ground-truth correctness. Human annotation and runtime schema/effect validation remain necessary.
5. **Baseline representativeness:** The current COLT and ToolScope variants are adaptations, as are other bounded or recorded-output baselines. The revision does not equate them with original published systems. Faithful reproduction is specified as a separate baseline family.
6. **Independent evaluator status:** A separate code implementation is not an independent oracle. E10 remains a labelled approximation over \(J_B\) and recorded goals.
7. **QoS evidence:** The current registries lack differentiated price and latency, and default values prevent meaningful QoS ranking. QoS advantage is not empirically established.
8. **Scalability:** The 100k result is on cloned contracts; the million-entry result is bitmap eligibility only. Neither supports a claim that the complete system scales to a million real tools.
9. **Model profile generalisation:** The 64-item/4-class calibration cannot validate the full conditional function across the wider task vocabulary. Generalisation is not claimed.
10. **Repair and reuse:** Deterministic repairs are evaluated; LLM assistant configurations and E21 experience reuse are not. Those capabilities remain proposed/implemented, not experimentally validated.
11. **Tampering coverage:** The original E14 logic skipped tamper whenever a task needed any effect. The new script does not make that class-level omission; it checks every attack class against task-required effect scopes and reports ambiguity separately.
12. **Advantage over eligible-only retrieval:** Existing confirmatory F3 does not establish superiority. The revision states this directly and requires matched-budget comparisons.

## Claim policy for the next manuscript

- **May be stated:** the formal propositions under their explicit assumptions; measured registry counts; benchmark retrieval results; the observed negative/inconclusive comparisons; deterministic implementation measurements; synthetic-scale measurements with their generator disclosed.
- **Must be qualified:** zero-exposure results based on simulated evidence; tool validity based on LLM labels; E10 joint feasibility; offline attack reachability; profile calibration; deterministic repair.
- **Must not be stated as demonstrated:** end-to-end task success, runtime attack prevention, actual sandbox-observed effect soundness, QoS advantage, LLM-assisted repair effectiveness, or experience-reuse benefit.

The original \`paper/sections/evaluation_final.tex\` is not overwritten. The revised draft is \`paper/revision_1/evaluation_revision.tex\`.