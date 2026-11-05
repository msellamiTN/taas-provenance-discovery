# Reusable Skill Registry v1

## Scope

The Skill Registry stores independently versioned, reusable planning guidance. A Skill is a declarative resource with a stable identifier, semantic version, bounded instructions, explicit trigger phrases, and optional tags.

## Resource contract

- apiVersion: taas.ai/v1alpha1, kind: Skill
- metadata: id, name, version, optional description
- spec.instructions: 1–8,000 characters
- spec.trigger_phrases: 1–20 unique case-insensitive phrases
- spec.tags: 0–20 unique normalized tags

Unknown fields are rejected. A Skill version is immutable once created.

## Lifecycle and evidence

draft -> validated -> published is monotonic. Each transition creates an append-only event containing actor, timestamp, transition, and immutable manifest digest. SQLite triggers reject mutation/deletion of version content and lifecycle events.

Validation is structural only. Publication means that a reusable guidance resource is available to the platform; it does not establish semantic correctness, trustworthiness, authorization, or execution readiness.

## API

- POST /api/v1/skills/validate
- POST /api/v1/skills
- GET /api/v1/skills?skill_id=...&limit=...
- GET /api/v1/skills/{skill_id}/versions/{version}
- POST /api/v1/skills/{skill_id}/versions/{version}/validate
- POST /api/v1/skills/{skill_id}/versions/{version}/publish
- GET /api/v1/skills/events?skill_id=...&limit=...

All endpoints require the Studio bearer token.

## Governance boundaries

- Skills contain untrusted operator-authored instructions; never put credentials or confidential values in them.
- Skills do not add tools to an Agent allowlist, expose the MCP registry, grant data access, authorize calls, or execute actions.
- Existing Agent-embedded skills remain supported for backward compatibility.
- Tenant isolation is not implemented by this single-service SQLite registry.
- v1 does not yet bind external Skill references into Agent manifests or resolve published Skills during decomposition. That is the next integration slice; until then, this registry is an independently managed resource API.
