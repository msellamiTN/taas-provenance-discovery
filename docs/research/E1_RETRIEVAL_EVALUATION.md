# E1 — Offline retrieval evaluation

## Purpose

E1 measures whether the current registry retriever ranks tools referenced by benchmark tasks near the top of its result list. It is a retrieval-only diagnostic, not an end-to-end task-success evaluation.

## Data separation

- **Ranking inputs:** each task's natural-language query and registry-derived capability renderings (tool name, server, class, description).
- **Registry modelling:** deterministic contract extraction from the pinned `data/processed/registry_merged.json` snapshot.
- **Evaluation-only labels:** task gold mappings are loaded separately and read only after a ranking has been produced.
- **No label feedback:** gold mappings, task categories, and unresolved names are not used to fit the encoder, build contracts, or calculate retrieval scores.
- **No upstream access:** the experiment uses the repository-retained processed snapshot; it does not fetch or clone an upstream benchmark.

The LSA encoder is fitted on registry tool documents only. The query is scored against this fixed tool index. Three ranking variants are compared: BM25 lexical, LSA dense, and reciprocal-rank fusion of BM25 + LSA.

## Ambiguous labels

A pipe-delimited mapping is one required group with any-of alternatives. For example, `server-a::search|server-b::search` is one gold group, not two required tools. A group is hit at the rank of its first retrieved alternative. Unresolved alternatives are excluded from the resolved-group denominator but counted in coverage diagnostics. Tasks with no resolved gold groups are reported and excluded from macro ranking metrics.

## Metrics

- **Group precision@k:** distinct required gold groups first hit in the top k, divided by k.
- **Group recall@k:** distinct required gold groups first hit in the top k, divided by the number of resolved gold groups.
- **MRR:** reciprocal rank of the first required gold group hit.
- **MAP:** average precision over first-hit ranks of resolved gold groups.
- **nDCG:** binary group relevance, where each group contributes once at its first alternative hit.

Metrics are macro-averaged over evaluable tasks per dataset. This makes each task equally weighted; it is not a micro-average over all gold mappings.

## Interpretation limits

E1 does **not** evaluate GoalSpec correctness, policy eligibility, type-filter precision, hypergraph composition, certificate validity, MCP execution, or semantic task completion. It does not prove that a retrieved tool can complete a multi-step task. The gold mappings themselves can be incomplete, ambiguous, or unresolved, so results must be interpreted against the reported resolved-label coverage.

This baseline intentionally isolates text retrieval. A subsequent experiment should evaluate the full request path with independently authored GoalSpecs and explicit policy configurations, while preserving a held-out evaluation boundary for gold labels.

## Reproduction

```bash
python experiments/e1_registry_retrieval.py --output results/e1_registry_retrieval.json
pytest -q tests/test_e1_registry_retrieval.py
```

GitHub Actions runs the experiment against the pinned processed snapshot and publishes the JSON metrics as the `taas-retrieval-evaluation` artifact.
