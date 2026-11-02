# TaaS Core Studio API (experimental)

This first API milestone exposes the existing TaaS discovery engine over HTTP. It deliberately does **not** execute MCP tools. MCP execution, user/workspace isolation, durable experiment storage and live trace streaming are later milestones.

## Install

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[studio]'
```

## Configure

Set a reviewed model-profile JSON path and a strong API token:

```bash
export TAAS_MODEL_PROFILE=/absolute/path/to/model-profile.json
export TAAS_STUDIO_API_TOKEN='replace-with-a-long-random-secret'
```

On PowerShell:

```powershell
$env:TAAS_MODEL_PROFILE = "C:\\path\\to\\model-profile.json"
$env:TAAS_STUDIO_API_TOKEN = "replace-with-a-long-random-secret"
```

Do not commit the profile if it contains private calibration data. Do not put tokens in notebook cells or source control.

## Run locally

```bash
uvicorn taas.studio.api:app --host 127.0.0.1 --port 8000
```

- Health: `GET http://127.0.0.1:8000/health`
- Readiness: `GET http://127.0.0.1:8000/ready`
- Discovery: `POST http://127.0.0.1:8000/api/v1/discover`

Discovery requires `Authorization: Bearer <TAAS_STUDIO_API_TOKEN>`.

## Request shape

```json
{
  "goal_spec": {
    "prompt": "Find public information about a topic",
    "prompt_inputs": ["text"],
    "goals": [
      {
        "id": "g1",
        "class": "search",
        "in": ["text"],
        "out": "document",
        "sigma": "data",
        "desc": "Search for relevant public information"
      }
    ]
  },
  "tools": [
    {
      "server": "example-server",
      "name": "search",
      "description": "Search public information",
      "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"]
      }
    }
  ],
  "policy": {
    "name": "studio-default",
    "required": [],
    "allowed": ["read(*)", "egress(*)", "session"],
    "lmin": "obs"
  },
  "engine": {}
}
```

This is a minimal API contract and the GoalSpec must conform to the current `taas.goals.parse_goal_spec` implementation. Tool schemas and descriptions are treated as declarations, not runtime proof.

## Colab

Use the deployment guide at `docs/deployment/COLAB_T4_CORE_STUDIO.md`. For this API milestone, use Colab CPU unless an explicitly GPU-backed extension is enabled. Bind the server to loopback and use an authenticated short-lived tunnel. Never expose this API without authentication.

## Current limitations

- One process, no multi-tenant authorization.
- No persistent experiment database.
- No MCP invocation endpoint.
- No frontend yet.
- No SSE/WebSocket event stream yet.
- No rate limiting or full production threat model.
- Model profile is configured server-side; callers cannot choose arbitrary filesystem paths.

## Browser workspace

The same-origin browser interface is available at `http://127.0.0.1:8000/` after starting the API. Enter `TAAS_STUDIO_API_TOKEN` in the password field and submit a JSON discovery request. The token is held only in page memory and is not written to local storage. The page displays the selected toolkit, abstention status, coverage gap, discovery latency and complete API response.

The interface is **discovery-only**. It does not execute MCP tools or run an agent. Treat tool metadata as untrusted input and do not submit secrets or sensitive arguments. The root page and health endpoints are not authenticated; for remote access, protect the entire service with an authenticated tunnel or identity-aware proxy.

## Google Colab

A pinned starter notebook is provided at [`notebooks/colab/taas_core_studio_colab.ipynb`](../../notebooks/colab/taas_core_studio_colab.ipynb). It installs the Studio extra, loads the API token from Colab Secrets, accepts a reviewed ModelProfile JSON file, and binds Uvicorn to loopback. It intentionally does not create a public tunnel. Remote access requires a separately configured authenticated access layer. Colab sessions are ephemeral; persist experiment records outside the runtime.
