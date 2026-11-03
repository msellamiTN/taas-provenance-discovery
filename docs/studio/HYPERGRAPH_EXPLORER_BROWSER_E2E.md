# Hypergraph Explorer — browser E2E acceptance

## Objective

Validate the shipped TaaS Studio frontend in Chromium against a live loopback FastAPI process. This is a browser-level acceptance layer above the existing unit, projection and TestClient tests.

## Browser journey

The Playwright test:

1. Starts the actual `taas.studio.api:app` with a test-only bearer token bound to loopback.
2. Opens the real Studio HTML and verifies the initial unavailable/empty projection state.
3. Authenticates through the Studio UI against the real runtime hardware endpoint.
4. Runs the built-in demo discovery request through the UI and requires a Core-generated `taas.hypergraph-projection/v1` response.
5. Checks `execution_performed=false` and inspects tool/vertex data in the UI.
6. Exercises the search filter, SVG keyboard selection, accessible entity-list selection and inspector.
7. Checks the narrow-screen stacked layout and captures a screenshot artifact.
8. Asserts that the browser made no HTTP requests to `/api/v1/mcp/*`.

## Safety boundary

- The built-in demo tool is a synthetic metadata contract, not a live MCP server.
- The discovery endpoint invokes the TaaS DiscoveryEngine only. No tool execution, MCP connection, authorization grant or production identity is exercised.
- The bearer token is generated for this local test process and is not a production secret.
- The server binds to `127.0.0.1` and is terminated after the test.
- This test does not claim cross-browser coverage, production deployment acceptance, visual design sign-off, screen-reader certification or security penetration testing.

## Run in Colab Runtime

Use `notebooks/colab/taas_hypergraph_explorer_browser_e2e_colab.ipynb`. The notebook pins an immutable source revision, installs the test/Studio extras and Playwright Chromium, runs the browser journey and displays its screenshot artifact.

## Acceptance evidence

A passing run means the exact browser journey above succeeded in the Colab runtime for the pinned revision. Keep the Colab output and GitHub Actions status distinct. A passing browser journey is not a replacement for the broader regression suite or human UX review.
