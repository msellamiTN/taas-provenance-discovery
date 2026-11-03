# Versioned MCP registry snapshots and Agent grant binding

## Purpose

The MCP registry workspace can inspect operator-configured stdio MCP servers using the protocol's `tools/list` operation and persist a content-addressed snapshot of the observed tool contracts. Agent publication can then resolve each declared `server_id/tool_name` grant against one exact snapshot and bind that immutable snapshot identifier to the Agent version.

This is a pre-execution integrity and configuration step. It does not invoke `tools/call`.

## API

All routes require the Studio bearer token.

| Method | Route | Behavior |
|---|---|---|
| POST | `/api/v1/mcp/registry/snapshots/inspect` | Inspect every configured server and persist one complete snapshot |
| GET | `/api/v1/mcp/registry/snapshots` | List stored snapshot IDs and counts |
| GET | `/api/v1/mcp/registry/snapshots/{snapshot_id}` | Retrieve exact snapshot and verify its content hash |
| POST | `/api/v1/agents/{agent_id}/versions/{version}/publish` | Publish configuration; requires `registry_snapshot_id` when tool grants exist |

## Snapshot construction

- Only operator-configured servers from the host MCP registry are eligible. Browser clients cannot supply executable commands, arguments, URLs or environment values.
- The inspection operation must explicitly report `inspection_only=true` and `tool_execution_performed=false`. Any mismatch aborts the entire capture.
- All configured servers are inspected before persistence. A failed or malformed server response prevents a partial snapshot from being stored.
- Tool names are validated; duplicate names per server and invalid input schemas are rejected.
- Each normalized tool definition is fingerprinted with SHA-256 over canonical JSON containing server ID, name, description, input schema, output schema and annotations.
- The complete snapshot is fingerprinted with SHA-256 over canonical JSON. The snapshot ID is deterministic for identical captured schema content; capture timestamps are stored separately.
- Snapshot rows are immutable in SQLite and their content hash is rechecked when read.

## Agent publication gate

For an Agent with a non-empty tool allowlist:

1. The caller must supply a stored `registry_snapshot_id`.
2. Every exact `server_id/tool_name` pair must exist in that snapshot.
3. The publication response returns each resolved tool's definition hash.
4. The Agent version is bound once to that snapshot ID; later rebinding is rejected.
5. The lifecycle audit event records the snapshot ID.

A missing snapshot returns HTTP 422. An unknown snapshot returns HTTP 404. A grant absent from the snapshot returns HTTP 409 and leaves the Agent in `validated` state. A tool-free Agent can still be published without a snapshot.

## Trust boundaries

- Snapshot existence is evidence that a configured server returned a schema during read-only inspection. It is not evidence that the tool works, is safe, or will behave as described.
- Tool definition hashes detect configuration/schema changes relative to the captured snapshot. They do not attest to server binary identity, runtime integrity, endpoint authenticity, or future behavior.
- Agent publication is configuration publication only. `tools_authorized=false` and `execution_enabled=false` remain explicit.
- No policy decision, human approval, runtime call authorization, MCP invocation, isolation, secret brokering, cancellation, quota enforcement or execution trace is implemented here.
- Snapshot and Agent persistence share the local SQLite file. This remains single-service storage without tenant isolation, encryption-at-rest, backup/restore or externally signed audit evidence.

## Operator flow

1. Configure stdio MCP servers on the API host using the existing MCP registry configuration.
2. Use the read-only inspect action to capture a snapshot.
3. Review the returned server/tool schemas and snapshot ID.
4. Create and structurally validate an Agent version.
5. Publish with the selected snapshot ID. Confirm every declared tool grant resolves and inspect the returned tool-definition hashes.
6. Treat the result as a published configuration—not an executable or authorized agent.
