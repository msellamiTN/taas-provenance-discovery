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

## v1.2 — Explainable Hybrid Retrieval

`taas.studio.tool_service` builds one cached `DiscoveryEngine` over the full
retained-registry contract set (`_tool_engine()`); the index, retriever and
hypergraph are shared across requests — retrieval state is never rebuilt per
call.

`POST /api/v1/tools/retrieve` → `taas.retrieval-explanation/v1`. Body:

| Field | Default | Meaning |
|---|---|---|
| `query` | — | Retrieval text (required) |
| `goal_output` | `null` | Optional type context (Θ type string) for the structural component |
| `eligible_tool_ids` | `null` | Restrict ranking to these `server::name` ids (unknown ids → `unknown_tool_ids`, never silently dropped) |
| `components` | `["lex","den","str"]` | Subset selection; any other value → 422 |
| `k` | `10` | 1–100 |
| `type_filter` | `true` | Drop zero-structural tools when `goal_output` set |
| `prompt_inputs` | `[]` | Reachability seed types for the structural component |
| `include_hypergraph` | `false` | Fold a filtered `taas.hypergraph-projection/v1` (v1.4) into the response |
| `policy` | `{}` | Optional eligibility policy — adds `eligible` flag per result |

Per result: `tool_id`, `rank`, `fused` score (== `HybridRetriever.scores()`
exactly), `component_scores` `{lex,den,str}`, `rrf_contribution`
(`1/(k0+rank)` per selected component), `eligible`, `serves_goals` when
`goal_output` is set. `score_semantics:
retrieval_relevance_only_not_capability_evidence_eligibility_or_authorization`.

## v1.3 — Eligibility Explanation

`POST /api/v1/tools/eligibility` → `taas.eligibility-explanation/v1`.
Mirrors `eligible_set` exactly; explains per tool:

- **positive encoding** — `required_properties`: strength vs `lmin`, `met`;
  rejection `required_property_below_strength:{prop}`
- **closed_world encoding** — `forbidden_properties`: strength vs `lmin`,
  `violated`; rejection `forbidden_property_at_strength:{prop}`
- **visibility** — `visible`; rejection `not_in_policy_visible_set`

Also returns the engine's full `eligible_ids` set and a summary
(`evaluated/eligible/rejected/unknown`). `eligibility_semantics:
policy_evidence_strength_only_not_relevance_capability_or_authorization`.

## v1.4 — Hypergraph Context on Retrieval

`include_hypergraph: true` on `/tools/retrieve` attaches
`hypergraph_projection` — a read-only filtered projection
(`project_hypergraph`) covering the returned top-K tools, their semantic
types, reachability and derivations. No new route; deterministic; no
authorization/execution effect.

## v1.5 — Registry-Backed Discovery

`POST /api/v1/objectives/discover` accepts `registry_tool_ids` as an
exclusive alternative to inline `tools` (both → 422; neither → 422). Each id
must resolve exactly against the retained registry (`server::name`); any
unresolved id → 422 with the list. Resolved contracts carry their registry
definition hash and provenance; the response marks `tool_source`.
