# Independent Certificate Audit — E10 support

**Status:** offline evaluator implementation; no E10 result is claimed.  
**Protocol authority:** `docs/experiment_design/pamcp_experiments_v1.json`, E10.

## Purpose

`src/taas/experiments/independent_certificate_audit.py` recomputes the six mandatory
pre-execution predicates from frozen inputs and compares them with the submitted
certificate's reported checks. It does not trust `Certificate.valid`, the submitted
check booleans, or the submitted witnesses as proof.

The audit recomputes:

| Check | Recomputed condition |
|---|---|
| S — sufficiency | Every non-optional goal has a witness under the frozen reachability semantics |
| C — consumability | Each selected output is consumable under the configured multimodal/artefact rule |
| P — producibility | Every selected tool's required input is satisfiable and credential prerequisites are held |
| E — effect bound | All scoped effects are allowed and no selected pair is forbidden |
| L — flow bound | The configured conservative/derivation information-flow check reports no violation |
| V — evidence | Under positive encoding, every required property reaches the trust threshold |

This follows the current `Certificate.valid` predicate: S, C, P, E, L and V are mandatory.
M (inclusion-minimality) and B (bridge ratio) remain diagnostics and are not silently
promoted to mandatory validity conditions.

## Audit output and failure behavior

- `recomputed`: independently evaluated boolean for each mandatory check.
- `reported`: corresponding value carried by the submitted certificate.
- `matches`: strict equality comparison; missing, non-boolean or contradictory values fail.
- `unknown_tools`: selected IDs absent from the frozen graph.
- `valid`: all recomputed mandatory predicates pass and all reported values match.

Unknown or duplicate selected tool IDs fail closed. No missing input, evidence record,
or policy condition is imputed.

## Independence boundary

The audit re-evaluates predicates from the frozen graph, goals, policy, model edges and
profile. It does not use the certificate producer's `valid` property or trust its check
booleans. It intentionally shares the domain's canonical primitive semantics
(`Hypergraph.reach`, scoped-effect coverage and flow-label primitives); therefore it is
an independent certificate *rechecker*, not an independently reimplemented formal
semantics or a proof of the correctness of those primitives.

It is an offline pre-execution contract audit. It does not establish actual runtime
effects, task success, or executed out-of-policy actions. Those protocol outcomes remain
separate and cannot be inferred from certificates.

## Tests

`tests/test_independent_certificate_audit.py` covers a matching certificate, a forged
reported E check, and an unknown selected tool. Test execution and CI status must be
reported separately from the existence of these test cases.
