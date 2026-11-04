
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


## Baseline method catalogue

The baseline catalogue is versioned separately at `docs/experiment_design/pamcp_baselines_v1.json` and currently defines 31 method cards/controls. Each card records the method family, approach, implementation maturity, parameter defaults, supported experiments and fidelity caveats.

Important executable adapters in `src/taas/experiments/baseline_runner.py` include:

- BM25 lexical ranking.
- Dense retrieval using the current LSA encoder (a documented surrogate, not BGE-M3).
- RAG-MCP-style global multi-query dense retrieval with reciprocal-rank fusion (clean-room adaptation; no official implementation is claimed).
- MCP-Zero hierarchical server-to-tool routing (single-pass adaptation; no active LLM request loop).
- Per-subtask hybrid retrieval and union.
- COLT-style scene co-use/completeness ranking, requiring training-only query/tool bundles.
- ToolScope-style similarity clustering and contextual representative selection, retaining original provider/tool IDs.
- CMTF-style typed precondition/effect breadth-first planning, returning stepwise frontiers and a cumulative union.
- AutoTool (AAAI 2026)-style confirmed trajectory reuse, restricted to E21 and requiring registry, policy and per-tool definition-hash revalidation.

Separate registry-side baselines for E2/E3 include structural-schema typing, schema-plus-lexical typing, annotation-only effects and lexical effects. The live probe baseline is blocked until an isolated MCP probe runner is deployed.

## Baseline routes

- `GET /api/v1/baselines/catalog` — list/filter baseline method cards; optional `kind` and `experiment_id`.
- `GET /api/v1/baselines/catalog/{baseline_id}` — method detail.
- `GET /api/v1/experiments/catalog/{experiment_id}/baselines` — only methods valid for that experiment.
- `POST /api/v1/baselines/preview` — run selected available adapters on a supplied GoalSpec and tool snapshot.

The preview request must include an experiment ID and baseline IDs permitted for that experiment. It reports adapter outputs, input registry hash and status. It does **not** access evaluator labels, invoke MCP tools, persist an E-series run or calculate benchmark scores. An adapter that needs unavailable training scenes, trajectory history or runtime capabilities returns a blocked status rather than fabricating an output.

Example request:

```json
{
  "experiment_id": "E8",
  "baseline_ids": ["bm25", "dense_lsa", "rag_mcp", "mcp_zero"],
  "goal_spec": {
    "prompt": "Search customer reviews",
    "prompt_inputs": ["query"],
    "goals": [{
      "id": "g1",
      "class": "search",
      "in": ["query"],
      "out": "record:review",
      "eff": ["read(reviews)"],
      "sigma": "data",
      "desc": "Search customer reviews"
    }]
  },
  "tools": [],
  "top_k": 5
}
```

Replace the empty `tools` array with the actual, frozen E8 registry subset. Never pass evaluator gold labels in this request.
