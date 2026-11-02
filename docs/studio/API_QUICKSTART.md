# TaaS Core Studio API (experimental)

This milestone exposes the existing TaaS discovery engine over HTTP. It deliberately does **not** connect to an LLM provider or execute MCP tools. Agent orchestration, sandboxed MCP invocation, durable experiment storage and live trace streaming are future milestones.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[studio]'
```

## Configure

Set a reviewed TaaS ModelProfile JSON path and a strong API token:

```bash
export TAAS_MODEL_PROFILE=/absolute/path/to/model-profile.json
export TAAS_STUDIO_API_TOKEN='replace-with-a-long-random-secret'
```

PowerShell:

```powershell
$env:TAAS_MODEL_PROFILE = "C:\\path\\to\\model-profile.json"
$env:TAAS_STUDIO_API_TOKEN = "replace-with-a-long-random-secret"
```

A conservative, syntactically valid example is [strict-empty.json](../../examples/model_profiles/strict-empty.json). It contains no calibration measurements, so strict mode assigns zero capability to unmeasured classes. It is a startup/abstention fixture, not a useful calibrated production profile.

**Important distinction:** `ModelProfile` is TaaS capability calibration data (model identifier, class-level measured performance, threshold and strictness). It is not a provider connection object. The current API has no LLM endpoint, provider key, temperature or inference configuration. Do not add provider credentials to this JSON.

## Run

```bash
uvicorn taas.studio.api:app --host 127.0.0.1 --port 8000
```

- Health: `GET /health`
- Readiness: `GET /ready`
- Discovery: `POST /api/v1/discover`
- Retained benchmark catalog: `GET /api/v1/bench/datasets`
- Benchmark task browser: `GET /api/v1/bench/tasks`
- Retained tool registry browser: `GET /api/v1/bench/tools`

Discovery requires `Authorization: Bearer <TAAS_STUDIO_API_TOKEN>`.

## Repository-retained MCP benchmark data

Studio browses the benchmark snapshot already committed in this repository. It does not clone or fetch an upstream benchmark repository.

- `GET /api/v1/bench/datasets` returns dataset counts, categories and merged registry statistics.
- `GET /api/v1/bench/tasks?dataset=livemcpbench&limit=25` pages through task prompts.
- `GET /api/v1/bench/tools?source=LiveMCPTool&limit=50` pages through retained tool metadata.

The task browser deliberately omits `gold_tools` and `gold_unresolved`. Gold labels are evaluator-only and must not be exposed to the goal analyst or discovery process. Registry annotations are returned as metadata and are not treated as trusted provenance evidence.

Supported dataset identifiers are `livemcpbench` and `mcptoolbenchpp`. Supported tool sources are `LiveMCPTool`, `MCPToolBench++` and `all`.

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

The GoalSpec must conform to the current `taas.goals.parse_goal_spec` implementation. Tool schemas and descriptions are declarations, not runtime proof. The API returns a discovery decision and sets `execution_performed: false`.

## Browser workspace and Colab

The same-origin browser UI is available at `http://127.0.0.1:8000/`. Enter the bearer token in its password field; the page keeps it in memory rather than local storage. The UI displays selected tools, abstention, coverage gap, discovery latency and the full API response.

For Colab-hosted operation, follow the [Colab T4 step-by-step guide](../deployment/COLAB_T4_QUICKSTART.md) and open [the notebook](../../notebooks/colab/taas_core_studio_colab.ipynb). The notebook launches this app inside the Colab VM. T4 visibility does not imply that TaaS discovery or an LLM is GPU accelerated. Optional external access requires a named Cloudflare Tunnel protected by Cloudflare Access.

## Current limitations

- No LLM provider adapter or model inference endpoint.
- No MCP invocation endpoint or agent loop.
- No SSE/WebSocket event stream.
- No durable experiment database.
- Single-process experimental API; no multi-tenant authorization or production threat model.
- The browser page and health endpoints are unauthenticated at the application layer; remote access must protect the entire hostname with an authenticated proxy/tunnel.
- Tool metadata and schemas are declarations; this endpoint does not prove runtime behavior.
