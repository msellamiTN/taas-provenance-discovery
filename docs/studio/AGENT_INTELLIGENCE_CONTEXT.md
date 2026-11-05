# Agent Intelligence Context

## Purpose

Agent Instructions and Skills are inputs to the actual Objective Analyst LLM request. They are not decorative manifest metadata. Studio resolves a saved immutable Agent version, composes its instruction context, selects objective-relevant skills, and supplies that context to both initial generation and bounded refinement.

## Manifest contract

`spec.instructions` contains persistent Agent-level guidance.

`spec.skills` is an optional list of versioned skill definitions bundled into the immutable Agent version. Each skill defines an identifier, name, semantic version, description, reusable instructions, and explicit `trigger_phrases`.

Example:

```json
{
  "id": "multi-source-date-difference",
  "name": "Multi-source date difference",
  "version": "1.0.0",
  "description": "Retrieve independent dates and calculate their difference.",
  "instructions": "Create one independent acquisition goal per independently sourced date. Create a separate exact computation goal depending on both acquisitions.",
  "trigger_phrases": ["year difference", "date difference"]
}
```

The v1 resolver selects a skill when one or more declared trigger phrases occur in the original objective, case-insensitively. This is deterministic and auditable, but lexical matching is not semantic relevance proof. Unmatched skills are not injected.

## Runtime flow

1. Studio selects a saved Agent ID and immutable version.
2. The API loads that exact version from the Agent registry and validates its manifest.
3. The context resolver selects matching skills and computes SHA-256 digests for Agent and skill instructions.
4. The Objective Analyst receives Agent instructions and selected skill guidance in its system context.
5. The same context is supplied to the bounded refinement attempt.
6. The API response includes `agent_intelligence_context` trace metadata: Agent identity/version, lifecycle state, manifest digest, instruction digest, selected skill IDs, skill digests, matched triggers, and resolver policy.

The trace does not echo the full instruction or skill text.

## Authority boundaries

Instructions and Skills influence LLM planning. They do not add tools to the Tool Allowlist, expose the MCP registry to the LLM, grant permissions, authorize tool calls, alter the canonical GoalSpec schema or semantic vocabulary Θ, override Objective Contract or deterministic Core validation, or enable execution.

Operator-authored context is marked as lower priority than the mandatory GoalSpec/Core contract. Core independently validates the generated proposal.

Treat instruction and skill text as untrusted configuration. Never place credentials or confidential values in these fields.

## Compatibility

Older Agent versions created before the `skills` field existed retain their original canonical manifest shape and remain verifiable. The resolver treats a missing skills field as an empty list.

## Current scope and next increment

Skills are currently embedded and versioned within an Agent manifest. A separate reusable cross-Agent Skill Registry, semantic skill retrieval, skill dependency management, and skill-level evaluation/approval lifecycle are not included in this increment. The lexical resolver is a transparent baseline that can be measured before introducing semantic retrieval.
