# Benchmark-derived capability hypergraph

This builder constructs the TaaS tool-capability hypergraph from the repository's pinned
**data/processed/registry_merged.json** snapshot. It does not rebuild the merged registry and
does not modify **data/**, historical **results/**, or **docs/RESULTS.md**.

## Build

From the repository root:

~~~bash
python -m pip install -e .
python scripts/build_benchmark_hypergraph.py \
  --outdir results/runs/benchmark-hypergraph-<unique-run-id>
~~~

The output directory must be new or empty. The command refuses to overwrite a non-empty
directory. It writes three files:

| File | Purpose |
|---|---|
| capability_hypergraph.json | Typed vertices and one directed capability hyperedge per MCP tool |
| benchmark_tasks.evaluation-only.json | Benchmark task queries and gold tool mappings, isolated from graph inference |
| build_report.json | Counts, dataset provenance and leakage-control declarations |

## Hypergraph semantics

For each tool definition t = server::tool, the builder extracts a contract c(t) and
represents it as a directed hyperedge:

~~~text
{ required argument type_1, ..., required argument type_n }
                    |
                    v
              output type
~~~

The hyperedge retains named argument positions, required/optional status, schema-derived and
lexical type confidence, scoped effects, MCP annotations, effect provenance, flow source label,
QoS defaults, and the canonical tool-definition fingerprint. Optional arguments remain attached
to the contract even though they are not part of the required tail.

Vertices are unique semantic types. Hyperedges are **not** collapsed when several tools share
the same input/output types: tool identity and definition hash remain distinct.

## Leakage and evidence policy

The graph is constructed with deterministic schema/lexical typing only:

- It does not use silver_labels.json or LLM-derived silver typing.
- It does not use benchmark task gold tool labels to infer a tool's capability.
- It does not infer observed runtime effects from tool descriptions.
- MCP annotations and lexical effect cues are retained with their provenance category.
- Benchmark gold mappings are written to a separate evaluation-only file.

A pipe-delimited gold mapping is preserved as one candidate-alternative group. Unknown candidate
IDs are retained and flagged as unresolved; they are not silently discarded to create a false
single-tool label.

**Interpretation limit:** the output is a static, benchmark-derived capability model. A lexical
effect or an MCP annotation is a claim, not proof of runtime behavior. Runtime effect claims require
hash-bound sandbox observations or trusted attestations. The default QoS values are placeholders,
not benchmark measurements.

## Validation and next experiment

Run focused tests:

~~~bash
pytest -q tests/test_benchmark_hypergraph.py
~~~

Then run the full test suite in an isolated environment. Before reporting benchmark results, verify:

1. the source commit and registry snapshot hash;
2. tool and server counts against data/processed/registry_merged.json;
3. unresolved and ambiguous gold mappings in the evaluation-only file;
4. no task labels appear in hyperedge contracts;
5. every edge's definition hash matches the source RawTool.definition_hash();
6. no runtime-safety claim is made from lexical or annotation evidence alone.

The builder creates the structural benchmark graph. It does **not** run the E0–E13 experiments,
probe live MCP servers, or certify that a tool behaves as its definition claims.
