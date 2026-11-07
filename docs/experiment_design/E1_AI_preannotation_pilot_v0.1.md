# E1 AI-assisted pre-annotation pilot v0.1

**Status:** exploratory pre-annotation artifact; NOT human annotation, NOT adjudicated, NOT ground truth, and NOT an E1 completion result.  
**Generated:** 2026-11-07  
**Input:** approved E1 annotator packet v1.1 (569 registry tool rows).  
**Candidate CSV SHA-256:** `b49059f25ab2579a33f87d48833f92aac773fbd4128dea970ddf52842682a845`

## Why this artifact exists

Human annotation is currently unavailable. This pilot provides a reproducible triage of the 569 tool metadata records without misrepresenting machine-generated candidates as human-validated reference labels.

## Preliminary counts

| Candidate status | Count |
|---|---:|
| Provisional `non_read_only=true` | 99 |
| Provisional `non_read_only=false` (retrieval/analysis wording only) | 299 |
| Unresolved / abstained | 171 |
| **Total** | **569** |

There are 19 records with blank descriptions. They are not automatically labeled read-only. The 171 unresolved records include missing or insufficient descriptions and records for which documented wording did not support a conservative candidate.

## Method

A deterministic lexical triage was applied to the tool name and description only:
- Explicit documented mutation verbs (e.g. create, update, delete, upload, publish) produce a *positive candidate*.
- Explicit documented retrieval/analysis verbs (e.g. get, fetch, list, search, inspect) produce a *provisional read candidate* only when no mutation verb is detected.
- All other records abstain.
- No `readOnlyHint`, registry category, inferred server behavior, runtime execution, or undocumented semantics are used.

This is a lexical candidate generator, not a semantic verifier. It can produce false positives and false negatives. Confidence values are heuristic flags, not calibrated probabilities. Reproduction code is in `experiments/e1/ai_preannotation_rules_v0_1.py`.

## Taxonomy caveat

The repository operational definition treats only `write`, `delete`, `exec`, and `money` as state-modifying. `read`, `egress`, and `session` alone are not state-modifying. The CSV's `effect_classes` values are candidate tags inferred from wording; they do not establish observed effects or runtime behavior.

## What this does and does not establish

**Established:** 569 metadata rows were processed; candidate/abstention counts above are reproducible from the supplied packet; the generated CSV has the stated SHA-256.

**Not established:** annotation correctness, precision/recall, reference-label validity, inter-annotator agreement, Cohen's kappa, runtime effects, or completion of E1. No scientific performance claim may use these candidates as ground truth.

## Protocol impact and next decision

Keep the approved human-reference E1 protocol unchanged. Record this pilot as a separate exploratory artifact. If human annotation remains impossible, the authors must explicitly approve a protocol amendment before any machine-generated labels can serve as reference labels. Such an amendment must specify the model/version, prompt and decoding settings, evidence rules, abstention policy, independent validation, and adjudication strategy. Until then, downstream experiments requiring E1 reference labels remain gated.

## Candidate CSV availability

The generated CSV is attached to the associated ChatGPT conversation as `PaMCP_E1_AI_Preannotation_Candidates_v0.1.csv`. Its SHA-256 is recorded above. It has **not** been committed to this repository in this commit; this report and the reproduction script are the GitHub artifacts.
