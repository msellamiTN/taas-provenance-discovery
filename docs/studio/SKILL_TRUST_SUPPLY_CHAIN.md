# Skill Trust & Supply Chain v1

Supply-chain provenance for reusable Skills: registry-attested signatures,
publisher identity, verified inspection, and immutable revocation. None of these
mechanisms grant tools, permissions, data access, authorization, or execution
rights — they make Skill provenance inspectable and let consumers refuse
untrusted guidance.

## Signatures

`POST /api/v1/skills/{skill_id}/versions/{version}/sign`

- Requires a `published`, non-revoked Skill version (otherwise 409) and a
  configured `TAAS_EVIDENCE_ATTESTATION_KEY` (≥32 bytes; missing → 503).
- The service attests a `publisher_signature` assurance-evidence record bound to
  `{skill_id, version, manifest_sha256}` — the exact immutable digest. A
  signature never transfers to a different version or manifest.
- `publisher_id` (optional, ≤128 chars) declares publisher identity; it defaults
  to the `TAAS_STUDIO_ACTOR` identity. `statement` (≤500 chars) is optional.
- **Scope honesty**: this is a *registry-attested* HMAC signature — it proves
  this Studio instance issued the record and that stored content is intact. It
  is not a portable third-party identity or a claim that the Skill is safe.

`GET /api/v1/skills/{skill_id}/versions/{version}/signature`

- Re-verifies integrity, attestation and freshness for every stored signature on
  the exact binding; `verified` is true only when at least one valid record
  exists. Invalid or expired records are listed under `invalid_records` and
  never count.

## Revocation

`POST /api/v1/skills/{skill_id}/versions/{version}/revoke`

- Body: `{"reason": "1-500 chars"}` (required, `extra=forbid`). Only `validated`
  or `published` versions can be revoked; drafts and unknown versions fail.
- Appends an immutable `skill_revocations` row plus a `skill.revoked` lifecycle
  event; a second revocation of the same version → 409. The Skill version itself
  is never deleted or mutated.

`GET /api/v1/skills/{skill_id}/versions/{version}/revocation` returns the record
or `revoked: false`.

## Consumption rules (fail closed)

| Operation | Revoked Skill |
|---|---|
| Agent `skill_refs` binding (direct or transitive via dependency DAG) | **Refused** — `AgentSkillBindingConflict` / `SkillDependencyConflict` |
| `POST .../sign` | Refused — 409 |
| `GET .../dependency-graph`, `GET .../hypergraph` | **Inspectable** — returns 200 with `revoked: true` on affected nodes (provenance remains readable) |
| `GET /skills` list, `GET .../versions/{v}` | `revoked: true` flag reported |

Rationale: revocation must block *new consumption* while preserving auditability
of *what was referenced and when*.

## Test coverage

`tests/test_skill_trust_supply_chain.py` — signature creation/verification,
digest binding, publish-only signing, key-missing fail-closed, revocation
immutability, binding refusal, and inspectable revoked DAGs.
