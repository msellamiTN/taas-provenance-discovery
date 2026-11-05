# Agent Release Readiness

## Purpose

The Release Readiness endpoint provides a deterministic, explainable assessment of an immutable Agent version before an operator considers publishing or promoting it. It is a diagnostic gate, not an authorization service and not an execution endpoint.

## API

Authenticated endpoint:

\`GET /api/v1/agents/{agent_id}/versions/{version}/release-readiness\`

The response includes:

- \`decision\`: \`READY\`, \`BLOCKED\`, or \`NEEDS_REVIEW\`
- \`checks\`: named Boolean checks
- \`blockers\`: machine-readable blocker codes and explanations
- \`warnings\`: non-blocking observations
- \`resolved_tool_grants\` and \`unresolved_tool_grants\`
- immutable Agent and registry snapshot identifiers

## Current checks

The engine verifies:

1. The stored manifest passes the strict Agent schema and is already in canonical normalized form.
2. The canonical manifest SHA-256 matches the immutable registry digest.
3. The Agent lifecycle is \`validated\` or \`published\`.
4. When tool grants exist, the bound MCP registry snapshot is present, its content hash matches its snapshot identifier, and every grant resolves to an exact tool definition SHA-256.

A missing, altered, or mismatched manifest/snapshot; an unvalidated lifecycle state; or an unresolved grant yields \`BLOCKED\`.

## Deliberate non-ready conditions

The current platform does not yet provide a trusted release evidence bundle store, an assessor-claim verification pipeline, or a trusted human approval workflow. The engine therefore records those checks as false and returns \`NEEDS_REVIEW\` for an otherwise structurally sound candidate.

The following are not proven by this release diagnostic:

- semantic correctness of the Agent's instructions or GoalSpec;
- hypergraph/capability composition consistency;
- trusted policy conflict analysis for the full release package;
- runtime deployment readiness or operational SLO compliance;
- human approval, authorization to call a tool, or successful execution.

These are explicit integration gaps, not implicit passes. The engine must not be changed to report \`READY\` until each required gate is backed by trusted evidence and independently validated.

## Security boundary

- The route requires the Studio API bearer token.
- Client-supplied claims cannot satisfy assurance or approval checks.
- The route does not create approval records, issue authorization tokens, invoke MCP tools, or enable Agent execution.
- Existing fail-closed authorization preflight remains authoritative for invocation decisions.
- The SQLite Agent registry is currently single-service persistence and does not provide multi-tenant isolation.

## Colab acceptance

The maintained notebook pins the implementation commit and includes:

- focused \`tests/test_release_readiness.py\` execution;
- creation and structural validation of a temporary Agent through the live Studio API;
- authenticated invocation of the release-readiness endpoint;
- assertions that the expected result is \`NEEDS_REVIEW\`, assurance and approval remain unverified, and execution remains disabled.

A notebook containing these checks is an acceptance procedure, not evidence that a live Colab run has already passed. Record actual runtime output before marking Colab acceptance complete.
