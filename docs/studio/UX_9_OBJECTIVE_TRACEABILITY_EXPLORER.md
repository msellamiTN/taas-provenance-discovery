# UX-9 — Objective Traceability Explorer

Status: implemented on `codex/ux9-objective-traceability-explorer`, stacked on UX-8 PR #84 head `64ab65b9d812ee4a96647e583bd8b12c052b7274`. The user approved the complete UX-9 mockup, including all represented views and interactions, before implementation.

## Objective and views

Provide an evidence-conscious workspace for inspecting objective traceability using the Core projection endpoint `POST /api/v1/hypergraph/objective-traceability`.

- Graph: SVG rendering of returned vertices and hyperedges; keyboard-operable entity selection.
- Lineage: explicit source/relationship/target rows.
- Relationships: relationship ledger with provenance.
- Evidence: source spans and explicit trigger observations when supplied.
- Export: download the exact returned projection JSON.
- Explorer input: paste a supported `taas.objective-skill-traceability/v1` record and request its projection.
- Inspector: inspect selected node or relationship fields.
- Filters: missing evidence, unresolved links, review required, and declared relationships only.
- Responsive layout and accessible tabs with ArrowLeft/ArrowRight/Home/End navigation.

## Data and governance contract

The browser does not synthesize a projection. It sends the supplied traceability object to the authenticated Core endpoint and renders only a response with schema `taas.hypergraph-projection/v1`. Graph placement is presentational only. Relationship links are taken from returned `source_vertex` and `target_vertex` fields; unresolved links are not repaired or inferred.

The workspace does not assert semantic correctness, goal fulfilment, authorization or execution. Evidence spans and lexical trigger matches remain provenance observations. No MCP tools are called or executed. No authorization is granted. Governed MCP execution and isolated workers remain disabled. The fixed experimental protocol and UX-2 through UX-8 are unchanged.

## Acceptance criteria

1. The five tabs render and switch with keyboard support.
2. A valid traceability object is sent only to the existing authenticated Core endpoint.
3. Only a schema-valid Core projection is rendered.
4. Selecting a node displays its available provenance/evidence fields.
5. Relationship ledger and lineage show only explicit returned references.
6. Missing/unresolved/review filters never create or repair graph links.
7. Export contains the exact projection object returned by Core.
8. Empty and error states do not display synthetic graph data.
9. No execution, authorization or semantic-proof claims are introduced.

## Validation status

Source-level regression checks are added. Full pytest, repository CI, browser interaction, accessibility and authenticated Colab acceptance must be run against the exact UX-9 head before acceptance. No merge or deployment is performed by this change.
