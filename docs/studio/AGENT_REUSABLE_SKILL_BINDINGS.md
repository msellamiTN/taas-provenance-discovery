# Agent bindings to reusable Skill Registry versions

## Purpose

Agent manifests may reference Skills managed independently by the TaaS Skill Registry. A reference is immutable and exact: it pins the Skill ID, semantic version, and canonical registry manifest SHA-256 digest. Floating aliases such as `latest` are not supported.

## Manifest shape

Add `spec.skill_refs` to an Agent manifest:

```json
{
  "skill_refs": [
    {
      "id": "date-difference",
      "version": "1.0.0",
      "manifest_sha256": "<64 lowercase hexadecimal characters>"
    }
  ]
}
```

A reference must resolve to an existing Skill version in lifecycle state `published`. The digest must exactly match the registry record. Missing, draft, validated-but-unpublished, or digest-mismatched references fail closed.

An Agent cannot embed a Skill and reference the same Skill ID simultaneously. Duplicate references are rejected. Existing manifests without `skill_refs` preserve their canonical representation.

## Lifecycle integration

- Agent manifest validation resolves all references against the registry.
- Agent draft creation rejects missing, unpublished, or digest-mismatched references.
- Saved Agent validation rechecks the exact references before the Agent transitions to `validated`.
- Agent publication rechecks references before publication.
- Objective preparation resolves the same immutable Skill versions and injects only objective-triggered instructions into the actual analyst context.
- The context trace records each external reference's ID, version, source, lifecycle state, registry manifest digest, selected status, and instruction digest. It does not expose instruction text in the trace.

## Studio workflow

The Agent manifest editor provides a published-Skill picker. Loading the picker reads the authenticated Skill Registry list endpoint. Adding a selection writes the exact ID/version/digest tuple into `spec.skill_refs`; it does not copy Skill instructions into the Agent manifest.

## Security and governance

Reusable Skill instructions are untrusted planning guidance. They do not grant tool allowlist entries, MCP visibility, data access, authorization, or execution rights. The Agent tool allowlist remains separate and is never passed to the LLM. The canonical GoalSpec and TaaS Core validation remain authoritative.

A Skill reference is a supply-chain pin, not a trust certificate. Publication currently represents registry lifecycle approval; it does not prove semantic correctness, safety, or suitability for every Agent. Tenant isolation is not provided by the current single-service SQLite registries.

## Current resolver

The existing deterministic trigger-phrase resolver remains in place. External Skills use the same case-insensitive substring policy as embedded Agent Skills. Semantic retrieval, dependency graphs between Skills, cross-tenant sharing, revocation policy, and signed publisher attestations are outside this increment.
