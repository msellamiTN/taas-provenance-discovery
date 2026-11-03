# Governed authorization preflight

## Purpose

The authorization preflight endpoint makes the boundary between published Agent configuration and a governed invocation explicit. It evaluates the server-side bindings that can currently be verified and returns a structured deny report for every missing prerequisite.

It is deliberately **not** an authorization grant. It does not issue approval tokens, call MCP `tools/call`, or start an execution worker.

## API

`POST /api/v1/agents/{agent_id}/versions/{version}/authorization/preflight`

Request fields:

- `server_id`: exact configured MCP server identifier
- `tool_name`: exact tool name
- `arguments`: invocation argument object (hashed, not executed)
- `goal_spec`: exact GoalSpec proposal (structurally validated and hashed)

The request rejects additional fields. In particular, clients cannot provide a principal, policy, effects, assurance hash, or approval state.

## Server-owned inputs

- `TAAS_STUDIO_PRINCIPAL`: configured service identity. The Studio bearer token is not treated as a human identity.
- `TAAS_STUDIO_POLICY_VERSION`: operator-controlled immutable policy version label.
- `TAAS_STUDIO_POLICY_JSON`: JSON policy object normalized into the existing `Policy` model. Its effective fingerprint is bound together with the policy version.

These values are loaded only from the API process environment. The browser cannot override them.

Example policy configuration:

```json
{
  "name": "docs-read",
  "allowed": ["read(docs)"],
  "required": [],
  "forbidden": [],
  "encoding": "positive",
  "lmin": "obs",
  "egress_threshold": "internal"
}
```

## Binding checks

The preflight binds or verifies:

1. Published Agent ID, version and immutable manifest hash.
2. The MCP snapshot ID already bound to that Agent version.
3. The exact declared `server_id/tool_name` grant.
4. The exact tool-definition SHA-256 in that snapshot.
5. The canonical GoalSpec hash and invocation-arguments hash.
6. The configured service principal and versioned policy fingerprint.

A missing or mismatched binding is a deny condition.

## Deliberate fail-closed boundary

The repository does not yet have a trusted effect-assessment pipeline or an assurance-evidence store with provenance/attestation semantics. Therefore, even when every existing binding check passes, the endpoint returns `decision: deny` with:

- `trusted_effect_assessment_pipeline_not_integrated`
- `assurance_evidence_store_not_integrated`

No browser-supplied effect declaration or evidence hash can satisfy these checks. No approval token is issued. This prevents a client from self-certifying its own tool safety or assurance evidence.

## Non-goals and production gaps

This milestone does not implement human identity federation, human approval UX, durable/distributed approval storage, policy signing, attested assurance evidence, MCP invocation, isolated workers, secret brokering, cancellation, quotas, or durable execution traces. The existing process-local `ApprovalStore` remains a primitive, not a production authorization service.

The next prerequisite is a provenance-backed assurance evidence contract and trusted effect assessor. Only after those are implemented and independently tested should an authorization grant be considered. MCP execution must remain disabled until the isolated executor and its operational controls are real.
