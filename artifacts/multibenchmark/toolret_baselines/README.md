# ToolRet baseline results

- Evaluated queries with qrels: **7,960** per system.
- Systems: BM25, TF-IDF, deterministic random sanity baseline.
- Cut-offs: 1, 5, 10.
- Metrics: Precision, Recall, MRR, nDCG, Hit.
- Results are copied from the completed Colab run; **no ranking or dataset acquisition was repeated** to generate this publication bundle.
- The notebook plotting cell reads `aggregate_metrics.json` and generates the figures without rerunning retrieval.

## Reproducibility

Source run commit: `83193a5c6b227cf68e92f5dd88e66ba533ac94fa`

ToolRet query revision: `b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445`

ToolRet tools revision: `e06c38c75612b6536bd959e08cdd345894aba6a7`

The full original run summary and raw rankings remain in the user's Colab artifact ZIP. This repository publication contains compact aggregate metrics, CSV, and vector plots.

## Scope and limitations

ToolRet is a heterogeneous tool-retrieval benchmark, not an MCP execution benchmark. These results compare lexical retrieval baselines only. They do not establish PaMCP superiority, semantic safety correctness, or real-world side-effect correctness. No confidence intervals are included in this publication bundle.
