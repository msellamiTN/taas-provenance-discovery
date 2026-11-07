# E18 — Factor semantics and interpretation boundary

## Current factorial factors

The current implementation exposes three factors:

- **G — model-conditioned capability gap:** whether the model profile's native capabilities are used to compute the capability gap.
- **P — provenance-aware eligibility:** whether provenance trust/evidence thresholds distinguish lexical/declarative evidence from observed or attested evidence.
- **S — joint set-level composition and assurance bundle:** whether PaMCP performs global toolkit selection, backward closure, joint compatibility/effect/flow checks and certificate generation.

## Important naming correction

The legacy variant identifier `PaMCP_NoCert` is retained for compatibility with existing experiment manifests. It must not be interpreted as a pure certificate ablation.

When S=0, the current runner also removes global set-level composition, backward closure and joint checks, replacing them with independent per-subgoal retrieval followed by union. Therefore S is a bundled mechanism, not certification alone.

The scientifically correct interpretation of E18 is the effect of the **joint set-level composition and assurance bundle**. Do not claim that E18 isolates the certificate generator.

## Comparability invariants

All eight cells must use identical:

- task IDs and task ordering;
- registry snapshot and tool visibility;
- model profile and model version;
- top-k and refinement budgets;
- principal, policy constraints and evaluator version;
- random seeds and timeout limits.

The runner must not read evaluator labels. Gold relevance, acceptable tool sets, unsafe references and oracle outcomes are loaded only by the evaluation layer after predictions are materialized.

## Future decomposition

A follow-up (2^4) study may separate joint composition from certificate validation. This is not required for the current (2^3) study, but the current results must retain the bundled interpretation.
