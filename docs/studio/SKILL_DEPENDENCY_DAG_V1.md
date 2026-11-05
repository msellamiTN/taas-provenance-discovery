# Reusable Skill Dependency DAG v1

## Purpose

A reusable Skill may depend on other reusable Skills through exact immutable references. The dependency graph is a composition contract for planning guidance; it is not a capability graph, trust certificate, authorization grant, or execution plan.

## Manifest contract

The optional `spec.dependencies` field contains up to 32 references:

```json
{
  "id": "date-arithmetic",
  "version": "1.0.0",
  "manifest_sha256": "<64 lowercase hexadecimal characters>"
}
```

Each dependency pins Skill ID, semantic version and canonical manifest digest. Floating aliases are unsupported. Duplicate Skill IDs and direct self-dependencies are rejected. Legacy Skill manifests that omit `dependencies` retain their prior canonical representation and digest.

## Resolution semantics

- The root Skill and every transitive dependency must exist in the registry, be published, and match its exact digest pin.
- Dependencies are returned in deterministic dependency-first topological order; a parent appears after its dependencies.
- Cycles, missing references, digest mismatches, unpublished versions, conflicting versions of one Skill ID, and malformed dependency records fail closed.
- Bounded resolution defaults to at most 32 distinct nodes, depth 16, and 128 edges.
- Shared dependencies are materialized once. An Agent cannot combine an embedded Skill and a registry dependency with the same ID.
- Resolved Agent context is additionally bounded by the existing 32-Skill and instruction-character limits.
- A deterministic graph SHA-256 commits to the root pin, node pins, edges and topological order.

## API

Authenticated read-only endpoint: `GET /api/v1/skills/{skill_id}/versions/{version}/dependency-graph`. It returns the exact root pin, dependency-first nodes, directed `depends_on` edges, topological order, deterministic graph digest, configured bounds and explicit non-authorization flags. Missing roots return 404; invalid, unpublished or inconsistent graphs return 409.

## Agent integration

Agent `skill_refs` continue to pin root Skill versions. During Agent lifecycle validation and Objective preparation, the resolver materializes each root and its transitive dependencies in dependency-first order. The root reference provenance includes the dependency graph digest and exact transitive dependency pins.

The current trigger-phrase selection behavior remains unchanged. Dependency resolution does not imply that every dependency will be selected for every objective.

## Governance boundaries

- A dependency edge does not grant tools, MCP visibility, data access, authorization or execution rights.
- Publication remains a registry lifecycle state, not a semantic or safety certification.
- Semantic correctness of composed instructions is not verified by the DAG resolver.
- Conflicting guidance is not automatically reconciled; it remains a review concern.
- Tenant isolation, publisher signatures, revocation and cross-tenant trust remain out of scope.

## Acceptance

`tests/test_skill_dependency_graph.py` covers legacy canonical compatibility, strict dependency pins, deterministic topological order, exact digest checks, unpublished dependencies, cycles, conflicting versions, graph bounds and Agent transitive materialization.


## Hypergraph Explorer integration

The authenticated endpoint `GET /api/v1/hypergraph/skills/{skill_id}/versions/{version}`
resolves the exact published root and its transitive dependencies through the
Skill Dependency DAG resolver, then projects that result into the shared
`taas.hypergraph-projection/v1` envelope.

The projection domain is explicitly `skill_dependency_dag`:

- Skill vertices preserve the exact ID, semantic version, canonical manifest
  SHA-256, lifecycle state, registry source and root/dependency role.
- Directed `depends_on` hyperedges preserve the source and target pins.
- The graph digest and deterministic topological order are carried as
  provenance metadata.
- Dependency edges explicitly have no authorization or execution effect.

The Hypergraph Explorer exposes a read-only Skill DAG inspector alongside the
existing semantic capability projection. It renders server-returned nodes,
edges and digests; it does not compute graph semantics in the browser.

This is a separate graph domain within the same projection envelope. Skill
nodes and dependency edges are not semantic data types, tools, model edges,
trust evidence, policy decisions, or execution routes. Invalid or unresolved
graphs fail closed (404 for missing records, 409 for inconsistent DAGs).
