# Hypergraph Explorer — Colab-hosted browser E2E acceptance

## Runtime topology

The browser E2E notebook is an add-on to `notebooks/colab/taas_core_studio_colab.ipynb`. Operators must first run the Core Studio notebook in a Colab runtime. That notebook owns repository checkout, package installation, Uvicorn lifecycle, ephemeral bearer token and Colab `proxyPort` URL.

The E2E add-on reuses the already-running `studio_process`, `api_token` and `proxy_url` from the same Python kernel. It must not start a second Uvicorn process, bind port 8000 again, install a second TaaS checkout, generate a replacement token, or expose another proxy.

## Browser journey

The Playwright test:

1. Attaches Chromium to the URL returned by the Core Studio notebook's Colab proxy cell.
2. Verifies the initial empty Hypergraph Explorer state.
3. Uses the exact temporary bearer token created by the Core Studio launch cell.
4. Opens **DISCOVER → Hypergraph Explorer** and clicks its own **Run discovery** action. The action reuses the existing discovery request/GoalSpec and calls the already-running API and real DiscoveryEngine.
5. Requires a server-generated `taas.hypergraph-projection/v1` projection and `execution_performed=false`.
6. Exercises filter/search, SVG keyboard selection, accessible entity-list selection and inspector details.
7. Tests desktop and narrow-screen layouts and writes screenshot artifacts under `/content/taas-e2e-artifacts`.
8. Asserts no browser requests to `/api/v1/mcp/*`.

## Safety boundary

- The built-in demo tool is synthetic metadata, not a live MCP server.
- Discovery uses TaaS Core; no tool execution, MCP connection, authorization grant or production identity is exercised.
- The API token is the current runtime token. The E2E notebook must never print its value or persist it.
- Colab's proxy remains the only access path used by this test; the API continues to bind to loopback inside Colab.
- This test does not claim cross-browser coverage, production deployment acceptance, screen-reader certification, security penetration testing or human visual sign-off.

## Run in Colab Runtime

1. Open `notebooks/colab/taas_core_studio_colab.ipynb` and run it in one Colab runtime.
2. Keep that same runtime/kernel and the existing TaaS Studio process alive.
3. If browser E2E is required, execute the E2E validation cells in that same runtime/kernel. They must attach to the existing `studio_process`, `api_token` and `proxy_url`; they must never launch a second Studio or require a second Colab runtime.

## Acceptance evidence

A passing run validates this browser journey against that currently running Colab Studio process. Keep the Colab operator output and GitHub Actions status distinct. A browser pass is not a replacement for the broader regression suite or human UX review.