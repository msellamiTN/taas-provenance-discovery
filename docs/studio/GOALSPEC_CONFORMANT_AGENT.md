# GoalSpec-Conformant Agent

## Purpose

The Agent decomposition step is not a free-form JSON formatter. It proposes a GoalSpec under the repository's canonical contract. The GoalSpec contract and semantic vocabulary Θ govern decomposition; model output is never authoritative.

## End-to-end contract

1. **Contract construction** — both Hugging Face and Ollama receive the same analyst guide, canonical Θ vocabulary, allowed goal classes, field semantics, and intent-preservation rules. The prompt explicitly prohibits invented types, domains, classes, effects, and claims of execution or correctness.
2. **Proposal** — the selected model returns one canonical GoalSpec JSON object. JSON parsing is only a syntax check.
3. **Deterministic validation** — the API checks the GoalSpec schema, supported classes, effect syntax, dependency DAG, and every prompt_inputs, in, and out type against the actual data/processed/theta.json kinds and domains. A syntactically plausible but undeclared type such as transactions or record:transaction[] is rejected.
4. **Intent diagnostics** — deterministic, conservative checks flag mismatches such as total/sum without aggregate/compute_exact, count without count, summary without summarise, finite retrieval estimates for an all request, missing numeric aggregation fields, and unspecified currency policy. These are heuristics, not a proof of natural-language equivalence.
5. **Bounded refinement** — when parsing, structural validation, or a severity=error intent diagnostic fails, the same provider receives the immutable original objective, the prior candidate, and diagnostics. At most one refinement is attempted. The original objective is repeated; the agent is instructed not to narrow or reinterpret it.
6. **Human review** — the API reports whether the candidate is structurally conformant and free of detected error-level diagnostics. It never auto-applies the candidate. Warnings remain visible. semantic_correctness_verified remains false.

## Interpretation of the user example

For “Calculate the total value of all transactions”:

- prompt_inputs: ["transactions"] is invalid: it is not a type in Θ. Use text for the natural-language objective unless an actual typed input is supplied.
- record:transaction[] is invalid unless transaction is added to the governed Θ ontology. The current vocabulary contains payment, but no transaction domain. Do not add a domain simply to make one model response pass.
- summarise is not an arithmetic reduction. A total requires an aggregate or compute_exact goal with numeric output.
- The aggregation must identify the numeric field (e.g. amount/value) or receive a numeric input type.
- all must remain in the retrieval scope. n is an estimate, not a completeness guarantee.
- If records may contain different currencies, the model must surface the policy ambiguity; it must not silently add unlike currencies.

The exact data model and business ontology determine whether record:payment[], record[], or another declared type is appropriate. The analyst must not invent a transaction schema.

## Response semantics

conformance.accepted_for_human_review means only that structural checks passed and no configured error-level heuristic fired. It does not mean that the decomposition is semantically correct, complete, authorized, or executable.

conformance.attempts is bounded to 1 or 2. auto_applied is always false. semantic_correctness_verified is always false. Existing discovery, authorization, and execution boundaries are unchanged; this feature does not invoke MCP tools or enable governed execution.

## Validation

The regression suite covers declared/undeclared Θ types, invalid business-noun prompt inputs, prompt contract injection, objective-preserving refinement, the one-retry bound, aggregation-vs-summary, count intent, all-scope warnings, and currency ambiguity. Live model quality still requires evaluation with the selected CPU/CUDA/Ollama model and operator review.
