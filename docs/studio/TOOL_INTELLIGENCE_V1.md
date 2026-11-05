# Tool Intelligence v1 / v1.1

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

## v1.1 — Registry Resolver + Capability Intelligence Profile

Registry-backed identity and per-tool capability intelligence, independent of
any discovery run (`taas.studio.tool_registry`).

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/tools` | Search retained-registry identities (`q`, `server`, `source`) — `taas.tool-identity/v1` |
| `GET /api/v1/tools/{server}/{name}` | Exact `server::name` resolve + **definition-hash verification** (stored hash recomputed via `RawTool.definition_hash()`); 404 unknown |
| `GET /api/v1/tools/{server}/{name}/intelligence` | Full capability profile — `taas.tool-capability-profile/v1` |

### Evidence-kind axis (declaration vs observation vs attestation)

`extract_contract(tool, store=EvidenceStore)` is the single evidence path —
the store's obs/att records upgrade the contract's `eff_record.ptype` exactly
as Core defines; lexical/annotation evidence is never claimed as verified.

| Axis | Source | Reported as |
|---|---|---|
| `declared` | Publisher schemas + annotations | present/not — **never trusted evidence** |
| `observed` | `EvidenceStore` obs records bound to `(tool, h(tool))` | `evidence_store_wired`, record counts, `observed_effects_present` |
| `attested` | Verified assurance evidence on `{tool_id, definition_hash}` | `verified_records` via lookup; `lookup_not_configured`/`lookup_failed` reported, never zero-claimed |

Profile contents: exact identity + hash verification, inputs (arg, type,
required, confidence), output type + confidence + assignment source,
`tool_class`, required credentials, `information_source_label`, QoS, tokens,
declared effects + evidence kind/method, provenance (source, category,
contract fingerprint). `structural_profile_only: true`; no invocation,
authorization, or execution implied.
