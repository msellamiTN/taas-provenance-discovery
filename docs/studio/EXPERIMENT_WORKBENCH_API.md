
# PaMCP Experimental Workbench — API Surface

The first implementation milestone exposes the workbench as a separate FastAPI application:
`uvicorn taas.studio.experiments_api:app --host 127.0.0.1 --port 8001`.

It is intentionally separate from `taas.studio.api:app` so the existing discovery API and browser flow are not disrupted. A later Studio shell can mount both services under one authenticated gateway after integration tests are in place.

## Implemented routes

- `GET /health`: public service health.
- `GET /api/v1/experiments/catalog`: authenticated E1–E22 catalog.
- `GET /api/v1/experiments/catalog/{experiment_id}`: a single experiment definition.
- `GET /api/v1/experiments/variants`: the four PaMCP system variants and eight factorial cells.
- `POST /api/v1/experiments/validate`: validate a run draft and return a configuration digest. This does not queue or execute.
- `GET /api/v1/experiments/workbench/status`: explicit capability readiness.

All endpoints except `/health` require `TAAS_STUDIO_API_TOKEN` as a bearer token. The service has no run database, worker, evaluator, or MCP sandbox yet. The API reports these as unavailable; it must not imply that validation equals experiment execution.

## Launch

```bash
pip install -e '.[studio,experiment]'
export TAAS_STUDIO_API_TOKEN='replace-with-a-strong-random-token'
uvicorn taas.studio.experiments_api:app --host 127.0.0.1 --port 8001
```

OpenAPI is available at `/docs` on the local service. Do not expose it over a public tunnel without authentication at the gateway.
