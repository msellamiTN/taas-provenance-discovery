# Google Colab execution — PaMCP definitive experiments

## Current execution target

The first Colab notebook is **E1 — Registry characterization**:

- Notebook: `notebooks/colab/PaMCP_E1_registry_characterization.ipynb`
- Source branch: `research/pamcp-experimental-v1`
- Input: `data/processed/registry_merged.json`
- Output root in Google Drive: `MyDrive/PaMCP_Experiments/E1/<run_id>/`

Open the notebook in Colab:

https://colab.research.google.com/github/msellamiTN/taas-provenance-discovery/blob/research/pamcp-experimental-v1/notebooks/colab/PaMCP_E1_registry_characterization.ipynb

Select **Runtime → Run all**. The notebook clones the branch, validates the experiment catalogue, installs declared dependencies, mounts Drive, runs E1, and packages a ZIP artifact.

## Artifact contract

Every E1 run creates:

- `summary.json` — descriptive E1 results and interpretation limits;
- `source_distribution.csv`;
- `category_by_source.csv`;
- `server_tool_counts.csv`;
- `annotation_key_frequency.csv`;
- `annotation_hint_distribution.csv`;
- `schema_type_frequency.csv`;
- `duplicate_names_across_servers.csv`;
- `category_by_source.png`;
- `inputs/registry_merged.json.gz` — exact frozen input snapshot;
- `inputs/SOURCES.txt` — pinned upstream source revisions;
- `MANIFEST.json` — Git commit, runtime information, input/script/catalog hashes and output checksums;
- a portable ZIP bundle.

The runner is metadata-only. It does not import `taas.realreg.truth`, load silver labels, inspect task gold labels, read LLM replay files, infer safety from names, execute an MCP server, or update experiment catalogue statuses.

## Sequential execution rule

Execute and validate one experiment before advancing to the next. The E1 notebook intentionally runs only E1. Do not mark E1 complete until its Colab ZIP, manifest, input hash, and output checks have been reviewed and retained.

E2 requires an independently annotated semantic-typing reference set. E3 requires credential-free runnable servers and a probe harness. E4–E7 require independent safety/evidence references and matched policy conditions. Later execution notebooks should be added only after those prerequisites are frozen.

## Re-run discipline

Do not overwrite an existing run directory. Every run receives a unique UTC run ID and a fresh hash manifest. Keep failed runs as diagnostic artifacts rather than silently replacing them. For a new code version, pin its new commit and create a new run.
