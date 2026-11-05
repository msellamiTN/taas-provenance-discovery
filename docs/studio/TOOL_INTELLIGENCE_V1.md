# Tool Intelligence v1

`tool_intelligence` — a per-candidate intelligence record attached to every
`POST /api/v1/objectives/discover` response (`taas.tool-intelligence/v1`).
It composes the discovery run's already-computed artifacts into one inspectable
view per tool:

```
goal served -> capability match (exact/uncertain) -> required inputs ->
effect profile vs policy -> composition neighbours -> assurance binding
```

## Per-tool record

| Field | Meaning |
|---|---|
| `serves_goals` / `derived_candidate` | Which goals retrieved it; whether it entered via backward-closure derivation |
| `capability_match[]` | Per goal: `match` (`exact`/`uncertain` per the composer's own `goal_match`), goal `out` vs tool output type, and **per required argument** which goal input types serve it (`served_by`) or `missing_inputs` |
| `effect_profile` | Declared effects, `policy_allowed` (all effects ⊆ policy allowed set), `forbidden_with` partners |
| `evidence` | `effect_evidence` provenance (e.g. `lex`), `property_strengths`, max strength vs `policy_minimum_evidence_strength`, `policy_evidence_met` |
| `composition` | `feeds`/`fed_by` — structural neighbours whose input/output types chain |
| `assurance` | `covered_by_selection_certificate` — true only for actually-selected tools under a valid certificate |

## Semantics

- **Structural only**: `match_semantics: structural_type_and_effect_compatibility_only`.
  Type/effect compatibility never asserts semantic correctness.
- No tool invocation: `tools_invoked: false`, `execution_performed: false`.
- Certificates bind the **selection**, not tool execution — `assessor_claim_truth_verified: false`.
- Unavailable diagnostics (e.g. engine without index) degrade to an honest
  empty record, not fabricated entries. Bounds: 64 tools / 32 goals.
