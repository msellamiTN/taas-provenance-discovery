# Hypergraph Explorer — Studio integration

## Purpose

The Hypergraph Explorer renders the read-only projection returned by the authenticated Discovery API. It is a view over the server-owned TaaS Core graph and its final reachability result, not a second graph engine in the browser.

## Data contract

The UI accepts only `taas.hypergraph-projection/v1` and reads:
- `vertices`: semantic types, Core-reported reachability, information labels and derivation metadata;
- `hyperedges`: tool and model capability edges, input/output types, effects, contract fingerprints, QoS and fired-in-reachability flags;
- `bridges`: bridge derivations recorded by the Core;
- `summary` and `projection_id`: projection metadata.

If the API reports `hypergraph_projection_status != available`, or the projection is absent or has an unsupported schema, the UI displays an explicit unavailable/invalid state. It never constructs a fallback graph from selected tools, GoalSpec, certificate bindings or browser state.

## Interaction

- Select a semantic type or hyperedge to inspect its returned attributes.
- Filter the entity list and visually de-emphasize non-matching graph rows.
- Use the accessible entity list as a keyboard-friendly alternative to SVG interaction.
- Inspect reachability and fired-edge state as returned by the Core.

The current layout is a deterministic presentation of hyperedge incidence, not a semantic graph layout algorithm. It does not calculate reachability, type compatibility, effects, information-flow propagation, composition, certification, authorization or execution.

## Trust and safety boundaries

- The authenticated API remains the source of the projection.
- Browser state is never accepted as authoritative graph or reachability input.
- An edge marked fired reflects the Core's recorded derivation; it is not evidence that an MCP tool was invoked.
- No tool invocation, authorization grant or execution state is implied by this explorer.
- Abstention or missing authoritative reachability yields an unavailable state, not a synthetic visualization.

## Validation

Static regression tests verify navigation, schema gating, field consumption, keyboard interaction and the absence of browser-side semantic claims. These tests do not replace browser automation, visual review, or an operator Colab run against a live Studio API.

## End-to-end API integration test

`tests/test_studio_hypergraph_explorer.py::test_live_studio_api_projects_real_core_discovery` exercises the real FastAPI application and real `DiscoveryEngine` using a local synthetic tool contract. It verifies the served Studio Explorer mount points, bearer-token rejection, authenticated Discovery response, Core-generated projection, reachable output type and `execution_performed=false`.

The fixture is contract metadata only. No MCP server is contacted and no tool is invoked.

## Numerical hardening: degenerate retrieval corpora

The Studio integration fixture contains a single registered tool. The previous LSA implementation requested at least two SVD components even when the fitted corpus had one row. In that case scikit-learn's explained-variance ratio has a zero denominator and emits `RuntimeWarning: invalid value encountered in divide`.

`LSAEncoder` now checks the across-document feature variance before fitting SVD. For a one-document or zero-variance corpus it uses normalized TF-IDF vectors directly; for non-degenerate corpora it retains truncated SVD. This keeps query and indexed vectors in the same representation and avoids hiding the warning with a global filter.

Regression tests cover one-document and duplicate-document corpora, finite normalized vectors, and preservation of the SVD path on a varied corpus. Browser automation, visual/keyboard review, deployment validation and production identity remain separate acceptance gates.
