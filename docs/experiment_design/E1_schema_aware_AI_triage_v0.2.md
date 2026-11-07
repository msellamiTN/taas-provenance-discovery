# E1 schema-aware AI-assisted triage v0.2

**Status:** exploratory machine-generated candidates only. This is NOT human annotation, adjudicated ground truth, runtime verification, or completion of E1.  
**Date:** 2026-11-07  
**Input:** 569-row E1 annotator packet v1.1, with the v0.1 lexical candidate fields retained.  
**Output:** `PaMCP_E1_AI_Semantic_Triage_v0.2.csv`  
**Output SHA-256:** `85be5ea4601f2b4358e3d140b9358ebb21fcdf10f4a11f79d345fa49be3cfe05`

## Results

| Triage outcome | Count |
|---|---:|
| Provisional `non_read_only=true` | 167 |
| Provisional `non_read_only=false` | 324 |
| Unresolved / abstained | 78 |
| **Total** | **569** |

Compared with v0.1, the schema-aware pass moved 102 previously unresolved rows into a candidate class. These are changes in machine triage coverage, not measured improvements in classification accuracy.

## Method

A deterministic, schema-aware evidence pass examined:
- tool name;
- tool description;
- JSON Schema property names;
- documented schema titles, summaries, and property descriptions;
- explicit HTTP method semantics when documented (POST, PUT, PATCH, DELETE).

The rules recognize documented English and selected Chinese operation terms. Explicit state-changing or execution cues produce a provisional positive candidate. Explicit retrieval/query/inspection wording, or documented computational/transformation wording without an explicit mutation cue, produces a provisional negative candidate. Ambiguous cases abstain.

The procedure does not call MCP servers, execute tools, inspect undocumented implementation code, or infer effects from `readOnlyHint` or registry category. The confidence column is heuristic and must not be interpreted as calibrated probability.

## Interpretation and limitations

This pass is more informative than the initial name/description-only lexical triage because it incorporates structured schema text. It remains a deterministic rule-based evidence extractor, not an independently validated semantic classifier. It can miss indirect effects, confuse examples with actual behavior, and fail on multilingual or underspecified documentation. A schema's parameter shape does not prove the server's runtime effect.

The operational effect taxonomy remains unchanged: only `write`, `delete`, `exec`, and `money` count as state-modifying; `read`, `egress`, and `session` alone do not. Candidate effect tags are inferred from documentation and are not observations.

## Reproducibility

Script: `experiments/e1/ai_preannotation_rules_v0_1.py` (updated with v0.2 schema-aware rules).

Run from the repository root:

```bash
python experiments/e1/ai_preannotation_rules_v0_1.py \
  path/to/PaMCP_E1_Annotator_A_v1.1/annotation_sheet.csv \
  PaMCP_E1_AI_Semantic_Triage_v0.2.csv
```

The script retains the original annotation fields and appends:
- `semantic_status_v0_2`
- `semantic_non_read_only_candidate_v0_2`
- `semantic_effect_classes_v0_2`
- `semantic_confidence_heuristic_v0_2`
- `semantic_evidence_rationale_v0_2`
- `schema_signal_excerpt_v0_2`

The CSV is attached to the associated ChatGPT conversation. It is not committed as a raw CSV in this report commit; its exact SHA-256 is recorded above.

## Protocol decision

This is an exploratory extension only. The approved human-reference E1 protocol is not silently replaced. Since human annotation is currently unavailable, the next scientific decision is whether the authors formally approve a protocol amendment defining machine-assisted reference construction, independent validation, abstention, and quality assessment. Until such an amendment is approved and validated, E1-dependent experiments remain gated and these candidate labels must not be used as ground truth.
