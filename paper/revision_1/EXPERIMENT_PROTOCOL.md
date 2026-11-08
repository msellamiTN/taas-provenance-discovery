# PaMCP revision 1 — experimental protocol

## Objective

The revised evaluation tests whether PaMCP improves the quality of toolkits made available to an LLM agent while maintaining a verifiable policy boundary. It separates discovery, evidence reliability, static certification and runtime execution.

The current E1–E22 results remain a historical baseline. New confirmatory hypotheses must be registered **before** the corresponding revised test outcomes are inspected. The scope-aware E14 re-analysis is exploratory because its estimand differs from the original F5.

## X1 — Independent contract/effect ground truth

**Purpose:** estimate the correctness of tool types, domains, scoped effects and private-source labels independently of the LLM labels used by the engine.

**Sampling:** draw a stratified tool sample across servers, operation/effect classes, annotation availability, schema completeness and domain types. A practical first annotation tranche is 200 tools; expand the sample if the uncertainty intervals are too wide for the claims.

**Annotation:** two independent annotators use a written ontology and effect-scope guide. Disagreements are adjudicated by a third reviewer. Annotators must not see \(J_A\), \(J_B\), the PaMCP eligibility decision, or the tool's ranking.

**Outputs:** exact input/output types, domains, cardinality, required arguments, scoped effects, private-source status, egress destination classes, uncertainty and evidence references.

**Metrics:** per-class precision/recall/F1, macro-F1, exact complete-type agreement, Cohen's \(\kappa\), Krippendorff's \(\alpha\) where appropriate, scope exact-match and adjudication rate. Report confidence intervals clustered by server.

**Gate:** no claim of semantic type/effect correctness based only on agreement between LLM-generated labels.

## X2 — Runtime effect and provenance validation

**Purpose:** estimate verifier false-accept and false-reject rates against independently observed effects.

**Environment:** isolated containers/VMs with controlled filesystem roots, network egress proxy, process tracing and disposable databases. Use credential-free tools first; credentialed tools require dedicated least-privilege test credentials and explicit approval.

**Ground truth:** actual filesystem, network, process, database and external-state traces bound to the exact tool-definition hash and server build. The probing input space and tested argument coverage must be recorded.

**Attacks:** forged annotations, laundered descriptions, changed definitions, missing annotations, description poisoning, name poisoning, malicious return content and adaptive server behaviour.

**Metrics:** false-accept, false-reject, effect-class and scope recall, probe coverage, cost per tool, time to detect a changed hash, and uncertainty by server/tool cluster.

**Gate:** simulated verifier FAR is not presented as measured FAR. Claims must be limited to the observed server/build/input envelope.

## X3 — Retrieval and typing diagnosis

**Purpose:** determine when type constraints improve or damage semantic relevance.

**Conditions:** BM25, dense retrieval, lexical+dense RRF, current PaMCP retrieval, relevance-first then structural filtering, confidence-gated structural reranking, human-corrected types, oracle goal types and oracle tool types.

**Controls:** same registry snapshot, identical query access, equal candidate/token budgets, and disjoint development/test tasks. Use official baseline implementations where available; report controlled adaptations separately. Tune each baseline with the same development budget.

**Metrics:** Hit@1/3/5, MRR, nDCG@k, group recall, candidate coverage, type-compatibility precision, feasibility among retrieved candidates and abstention.

**Strata:** registry size, tool-disjoint and server-disjoint splits, type confidence, ontology class, domain mismatch, and task complexity.

**Gate:** no assertion that structural ranking improves retrieval unless its improvement over relevance-only ranking is demonstrated on the held-out split.

## X4 — Scope-aware static security and manifest audit

**Purpose:** evaluate possible policy violations without pretending that offline reachability is executed attack success.

**Attack set:** always enumerate exfiltration, destruction, execution, payment and tampering. Never drop tampering merely because a task legitimately requires some other effect class.

**Policy:** extract the actual target scope from the task requirement. A requirement such as \`write(/reports)\` must not be widened to \`write(*)\`. A bare class with no target is classified as ambiguous, not as blanket permission.

**Effect assessment:** each tool effect is classified as:
- permitted: explicitly covered by a task-required effect scope;
- violation: the effect is outside the task's required effect scope;
- indeterminate: the reference labels lack the scope information needed to decide.

Indeterminate cases are not counted as safe. Report a conservative upper bound (violation OR indeterminate) separately from definite violations.

**Manifest:** serialize the actual manifest returned by the discovery pipeline and scan all model-visible fields for known canary payloads. Audit descriptions, names, argument keys and schema descriptions separately. A test of the \`sanitise()\` function alone is not called an end-to-end attack test.

**Metrics:** definite out-of-scope reachability, indeterminate scope exposure, conservative possible exposure, canary leakage by field, toolkit size and utility.

## X5 — Executable end-to-end composition

**Purpose:** measure whether an agent using the exposed toolkit completes the requested service task.

**Tasks:** multi-step tasks with explicit expected output artefacts and independent validators. Include read-only, scoped-write, egress, private-source and cross-tool composition cases.

**Systems:** PaMCP, eligible-only per-subtask retrieval, strong retrieval baselines, no-filter catalogue and runtime-enforced PaMCP. The same execution agent/model and runtime budget must be used for all systems.

**Metrics:** exact task success, partial completion, call success, argument validity, schema compliance, output correctness, actual effect violations, data-flow violations, repair/retry count, abstention precision/recall, end-to-end latency and total cost.

**Logging:** tool definition hash, server/build identity, principal, policy, exposed manifest hash, every attempted/accepted/blocked call, arguments with secrets redacted, result schema, effect trace and final artefact validation.

**Gate:** certificate validity and task success are separate outcomes. Do not infer one from the other.

## X6 — QoS and multi-objective composition

**Purpose:** exercise the cost/QoS objective on non-identical real or controlled QoS values.

**Design:** for each functional role, provide multiple semantically compatible service alternatives with independently measured price, latency and failure rate. Include rate limits, capacity, availability and correlated failures where possible.

**Metrics:** feasibility, expected cost, p50/p95 end-to-end latency, empirical reliability, toolkit size, Pareto dominance and optimality gap against an exact solver on tractable instances.

**Gate:** the current registry has no differentiated QoS; current E20 cannot establish QoS advantage.

## X7 — Realistic scale and evolution

**Purpose:** evaluate the complete engine under heterogeneous registry growth, not only bitmap membership.

**Registry sizes:** use actual heterogeneous snapshots where possible; synthetic scaling must preserve realistic distributions and include controlled variation of schema, effect, type and dependency densities.

**Factors:** servers, tools/server, duplicate rate, annotation sparsity, effect mix, shared-type density, forbidden-pair density and update rate.

**Metrics:** contract extraction, index build, risk-relation build, memory, eligibility, retrieval, composition, p50/p95 total request latency, concurrent throughput, update latency, invalidation precision/recall and recovery time.

**Compare:** eager, lazy, incremental and on-demand risk-relation construction.

**Gate:** bitmap-only microbenchmarks and cloned-contract runs are reported separately from full-engine measurements.

## X8 — Refinement and experience reuse

**Purpose:** establish whether counterexample-guided repair and revalidated experience improve recovery.

**Conditions:** no repair, deterministic repair, LLM-proposed repair without certification (diagnostic only), LLM-proposed repair with mandatory re-certification, and oracle repair. For reuse: cold discovery, cached pattern with full revalidation, stale registry, changed model, changed principal and revoked tool.

**Metrics:** repair success, new invalidity introduced, repeated counterexamples, iterations, abstention after budget, recall change, task success, reuse hit rate, revalidation cost, latency and cost.

**Gate:** patterns may seed decomposition but never bypass current eligibility, hash and certificate checks.

## Statistical plan

- Register primary hypotheses and practical margins before confirmatory test runs.
- Use task as the sampling unit for task-level outcomes; attack categories nested within a task must not be treated as independent tasks.
- Use server/tool-cluster bootstrap for registry-level annotation/effect metrics.
- Use paired task-level permutation tests for paired method comparisons.
- Use cluster bootstrap confidence intervals and report all exclusions/missingness.
- Apply Holm correction to the predeclared confirmatory family; all other analyses are exploratory.
- Report effect sizes, 95% intervals, exact \(n\), cluster counts and analysis units.
- Repeated random splits of the same sample are stability analyses, not independent replication.
- Preserve all seeds and per-item records.

## Completion and publication gates

1. X1 completed before making semantic-correctness claims.
2. X2 completed before presenting measured verifier performance.
3. X3 completed before claiming structural retrieval superiority.
4. X4 completed before making static attack-resilience claims beyond the current label proxy.
5. X5 completed before claiming end-to-end composition effectiveness.
6. X6 completed before claiming a QoS advantage.
7. X7 completed before claiming realistic full-engine scale.
8. X8 completed before claiming LLM repair or experience-reuse benefit.

Blocked items must remain explicitly blocked in the paper; do not create surrogate numbers.