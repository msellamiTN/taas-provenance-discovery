# Objective-to-Skill Traceability v1

`objective_skill_traceability` — a unified provenance record attached to every
`POST /api/v1/objectives/prepare` response. It composes the deterministic
artifacts that already exist into one inspectable chain:

```
objective clause span -> derived outcome (v3) -> GoalSpec goal (coverage)
                      -> triggered skill (exact pin) -> clause span
```

## Structure

| Field | Contents |
|---|---|
| `objective_sha256` | Digest of the immutable objective text |
| `clauses` | v3 clause ids, exact source spans, bound `outcome_refs` |
| `outcome_provenance` | Per outcome: `clause_ref`, `source_evidence` spans, coverage status, `covered_by_goal_ids`, and `skills_triggered_in_clause` |
| `skill_selection` | Per considered skill: `selected`, `matched_triggers` with **exact occurrence spans + `clause_ref`**, `instructions_sha256`, `registry_manifest_sha256`, `source`, `selection_policy` |
| `goal_provenance` | Per covered goal: linked outcome, clause, and skills triggered in that clause |
| `coverage_summary` | Required/covered/missing counts from outcome coverage |

## Semantics (conservative by construction)

- **Lexical linkage only**: a skill is associated with a clause because a
  declared trigger phrase occurs *inside that clause's span* — never asserted to
  have produced the outcome, the goal, or any capability.
- `provenance_scope: lexical_trigger_and_clause_binding_only_not_semantic_proof`
- `semantic_correctness_verified`, `tools_authorized`, `execution_enabled`
  remain `false`; human review stays mandatory before discovery.
- Without an Agent context the record still emits — `skill_selection: []`,
  `agent_context_status: not_configured` — so every prepare carries the same
  provenance shape.

## Consumer uses

- Explain *why* a skill was injected (which phrase, where in the objective).
- Audit which outcomes a model's GoalSpec covers and which clauses they trace to.
- Pin every skill to `manifest_sha256` / `registry_manifest_sha256` for
  supply-chain verification (complements `SKILL_TRUST_SUPPLY_CHAIN.md`).
