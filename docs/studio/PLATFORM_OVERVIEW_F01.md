# F01 — API-backed Platform Overview

## Purpose

Provide an actionable landing workspace for TaaS Studio using existing authenticated TaaS Core APIs. This is an incremental extension of the Studio UI at the pinned baseline; it does not replace the application shell or add backend routes.

## Data sources

| Display | Endpoint | Meaning |
|---|---|---|
| Agent versions | `GET /api/v1/agents?limit=100` | Number of returned immutable Agent version records (maximum 100) |
| Skill versions | `GET /api/v1/skills?limit=100` | Number of returned immutable Skill version records (maximum 100) |
| Registered tools | `GET /api/v1/bench/tools?source=all&limit=1&offset=0` | Core-reported registry total |
| Configured MCP servers | `GET /api/v1/mcp/servers` | Number of configured server entries; not a live connectivity check |
| Benchmark datasets | `GET /api/v1/bench/datasets` | Number of repository-retained dataset descriptors |

The overview also shows up to five recent Agent and Skill version records using exact IDs, versions, manifest digests, timestamps and lifecycle states returned by Core.

## Failure behavior

- Each endpoint is requested independently with `Promise.allSettled`.
- Partial API failure does not hide successful sources.
- Failed sources display `Unavailable` and their error message.
- The overall status distinguishes all-success, partial-success and total failure.
- Values are never inferred from unavailable sources.
- Dynamic values are rendered with DOM `textContent`; no API value is inserted as HTML.
- Refresh requires the existing Studio bearer token. The token is not persisted by this feature.

## Explicit non-guarantees

- Agent and Skill counts are returned records, capped at 100; they are not asserted to be global totals.
- MCP entries are configured servers, not verified connectivity or successful inspection.
- Model inventory is not shown because the current Model API is search-driven rather than a platform-owned inventory listing.
- No readiness, trust, policy, authorization, semantic correctness or execution decision is inferred.
- Refresh does not load models, inspect MCP servers, run discovery or invoke tools.

## Validation

Run:

```bash
python -m pytest -q tests/test_platform_overview.py
```

The suite checks UI targets, existing endpoint contracts, partial-failure handling, safe rendering and governance wording. Full repository CI and Colab acceptance are separate release gates.
