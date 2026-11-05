# Studio Governance Policy Engine v1

`taas.studio.policy_engine` composes the existing governance decision surfaces
into **one deterministic, typed verdict** per governed subject — instead of
scattered flags consumers must interpret themselves.

`allow` / `deny` / `needs_review` is a *diagnostic* verdict: it never grants
authorization or execution (`execution_enabled` / `authorization_granted`
remain `false`).

## What it is not

- `taas.policy` — effect/declassification rules for tool *composition* (unchanged)
- `execution_gateway` — one-time approval tokens (unchanged)
- `release_readiness` — one of several input surfaces, not the verdict itself

## Rules (v1, fixed set)

| Rule | Severity | Denies/reviews on |
|---|---|---|
| `structural_contract_valid` | blocking | Objective contract v3 invalid → deny |
| `skills_resolvable_not_revoked` | blocking | Missing/revoked bound skill, or binding resolution error → deny |
| `publisher_signatures_verified` | blocking | `signature_required` skill with unverified signature → deny |
| `trusted_evidence_verified` | review | No verified evidence, or invalid records present → needs_review |
| `release_gate_ready` | review | Readiness ≠ READY, or unavailable → needs_review |
| `authorization_preflight_authorized` | review | Preflight denied/unavailable → needs_review |

Unknown facts evaluate as `needs_review`, never `allow`. Subject kinds scope
applicability (`agent_version` skips contract/preflight rules — reported
`not_applicable`, not silently omitted).

## Conflict analyzer

When surfaces disagree, `conflicts[]` explains and resolves safest-first:
`readiness_vs_trust_conflict` (gate READY but a blocking rule fails → deny wins)
and `stale_facts_warning` (READY but review rules fail → verdict follows fired
rules, not the gate label).

## Endpoints

- `POST /api/v1/policy/evaluate` — `{subject, facts}` → verdict over
  caller-asserted facts (`facts_source: caller_asserted`). For testing/tools.
- `GET /api/v1/agents/{id}/versions/{v}/policy-verdict` — verdict over
  **registry-assembled** facts (readiness + evidence counts + per-skill
  trust incl. revocation & signature status). `facts_source: registry_assembled`.

`TAAS_POLICY_REQUIRE_SIGNATURES=1` makes publisher signatures blocking.
