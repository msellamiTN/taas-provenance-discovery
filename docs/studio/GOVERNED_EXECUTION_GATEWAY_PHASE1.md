# Governed Agent Execution Gateway — Phase 1

## Scope

This increment adds **authorization primitives only**. It does not invoke MCP tools, start MCP processes, or expose an execution endpoint. The existing Studio MCP workspace remains inspection-only.

The primitives reuse the existing TaaS scoped-effect model (taas.effects) and policy allow-set (taas.policy). They intentionally do not reinterpret MCP annotations as trusted evidence.

## Invocation authorization sequence

1. Resolve the server and tool from the operator-managed MCP registry.
2. Obtain the tool definition from a fresh server-side inspection and bind its definition hash to the proposed invocation.
3. Build effects from the TaaS capability contract and its provenance. Unknown, empty, or malformed effect declarations must be rejected, not treated as read.
4. Obtain the active policy from trusted server configuration. A browser-supplied policy is not authoritative.
5. Require the proposed effects to be fully covered by the policy's scoped allowed set.
6. Issue a short-lived, one-time approval token bound to actor, server, tool, exact JSON arguments, GoalSpec, and effective policy fingerprint.
7. On invocation, consume the token and re-check every binding. Any mismatch, expiry, or replay fails closed.
8. Only after those checks may a future managed MCP session call tools/call.

## Current implementation

src/taas/studio/execution_gateway.py provides canonical SHA-256 hashing for JSON-compatible values; an effective policy fingerprint; fail-closed scoped-effect authorization; process-local, thread-safe, expiring, one-time approval tokens; and exact binding to actor, server ID, tool name, arguments, GoalSpec and policy.

The approval store retains only a keyed token digest, not the raw token. A token is consumed even when a binding check fails, preventing retry with modified context. The store is process-local; a restart invalidates outstanding approvals.

## Important limitations

- **No MCP invocation is implemented in this phase.**
- There is no persistent or managed MCP process/session lifecycle yet.
- Current Studio bearer-token authentication is not a multi-user identity system. The future gateway must bind approvals to an authenticated principal, not a caller-selected actor string.
- Policy construction must move to trusted operator configuration before any invocation endpoint is enabled. The existing discovery endpoint accepts a policy payload for discovery; that must never be reused as execution authority.
- TaaS contract effects may be inferred from lexical evidence or annotations. Before execution, policy evaluation must use conservative effect handling and explicit provenance thresholds. An annotation alone cannot establish safety.
- The process-local store is not suitable for multiple workers, distributed deployment, or production multi-tenancy. Use a durable transactional store with atomic consume semantics for that deployment.
- Approval is not a proof that a tool is safe, semantically correct, or will satisfy the GoalSpec. It is an authorization decision for one exact invocation.

## Tests

tests/test_execution_gateway.py covers missing policy, empty/denied effects, scoped effect matching, binding mismatch, argument tampering, policy changes, one-time consumption, and side-effect denial.

The tests do not establish live MCP compatibility or production security.
