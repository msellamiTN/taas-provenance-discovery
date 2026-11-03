# Tools & MCP Studio

## Purpose

This increment adds a real, read-only MCP connection workflow to TaaS Studio:

1. The API operator configures trusted MCP stdio server launch definitions.
2. Studio lists configured server identities without exposing commands or credentials.
3. An authenticated user asks the API to launch one configured server and perform MCP initialization plus `tools/list`.
4. Studio renders the live tool names, descriptions and input JSON Schemas.
5. The user selects tool contracts and adds their metadata to the TaaS discovery request.
6. TaaS discovery evaluates the declared metadata. No `tools/call` request is made.

## Configure servers on the API host

Install the optional MCP SDK:

```bash
pip install -e '.[studio,mcp,test]'
```

Create a private JSON file outside the repository, for example `/etc/taas/mcp-servers.json`:

```json
[
  {
    "id": "filesystem",
    "name": "Workspace Filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
    "env": []
  },
  {
    "id": "internal_search",
    "name": "Internal Search",
    "command": "python",
    "args": ["/opt/taas/mcp-servers/search_server.py"],
    "env": ["INTERNAL_SEARCH_API_KEY"]
  }
]
```

Set the registry file path and provide secret values through the API process environment:

```bash
export TAAS_MCP_SERVERS_FILE=/etc/taas/mcp-servers.json
export INTERNAL_SEARCH_API_KEY='provided-by-secret-manager'
```

Alternatively, set `TAAS_MCP_SERVERS_JSON` to the JSON text. Do not set both registry variables.

The `env` field is a list of environment-variable **names**. The API resolves their values from its own process environment and passes only those named values to the configured child process. Secret values are never part of the browser payload or the registry response.

## Configuration and security model

- Only operator-configured `stdio` servers are supported in this increment.
- The browser cannot supply a command, arguments, URL, environment key, or secret.
- Server definitions are trusted operator configuration. Protect the registry file and API host accordingly.
- Server IDs must be unique, short identifiers.
- The child process is launched without a shell; command and arguments are passed as an argv vector.
- The configured server process is started for inspection and shut down when the inspection context exits.
- The registry response returns IDs, display names, transport and whether required environment variables are present. It does not return command lines or secret values.
- A connection timeout is enforced.
- Tool schemas and annotations are untrusted declarations. They are not evidence that the implementation behaves as described.
- Do not expose this single-user Studio API directly to untrusted tenants. A production deployment needs workspace-scoped authorization, process isolation, resource limits, audit logging, and secret-manager integration.

## API

All endpoints require the Studio bearer token.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/v1/mcp/servers` | List configured server metadata |
| POST | `/api/v1/mcp/servers/{server_id}/inspect` | Launch configured server and call initialize + tools/list |

An inspection response explicitly includes:

- `inspection_only: true`
- `tool_execution_performed: false`
- `tools[]` with server ID, tool name, description, input schema, optional output schema and annotations.

## TaaS boundary

MCP inspection is not tool execution. Importing a tool into a discovery request only makes its declared contract available to the TaaS discovery engine.

This increment does not:

- invoke `tools/call`;
- authorize side effects;
- establish provenance or behavioral correctness;
- certify task fulfillment;
- create an autonomous agent loop.

Future agent calls must be routed through a dedicated TaaS execution gateway that performs policy checks, approval where required, input validation, bounded execution, output validation and trace recording. Discovery certificates remain pre-execution evidence.

## Current limitations

- stdio only; Streamable HTTP and SSE transports are not included.
- Registry is operator-managed JSON, not yet a persistent GUI-managed server catalog.
- No server process pool or long-lived session reuse; inspection launches a fresh process.
- No resource/prompt browser yet.
- No MCP tool invocation yet.
