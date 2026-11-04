# PaMCP E1 execution runbook

## Protocol contract

E1 measures three distinct registry views from the exact source revisions pinned in \`data/raw/SOURCES.txt\`:

- LiveMCPTool: 525 tools / 69 servers.
- MCPToolBench++: 87 tools / 10 servers.
- Merged registry: 569 tools / 76 servers.

The source registries overlap. Do not report 525/44 as the original source sizes: 44 is the MCPToolBench++ contribution retained in the de-duplicated merged view.

The combined source registries must expose the protocol's 14 server categories. The run reports category counts for each of the three registry views, tools per server, description length, annotated-tool share, declared read-only share, and the independently reference-labelled non-read-only share.

## Reproducible run

The GitHub Actions workflow \`.github/workflows/e1-protocol-run.yml\`:

1. Preserves the committed merged registry before any rebuild.
2. Fetches LiveMCPBench commit \`36a51a1065dda49c1e503b87edf33a1e0b331a74\` and MCPToolBench++ commit \`2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037\`.
3. Rebuilds the three views from raw source inputs.
4. Compares every previously committed tool hash against the production \`RawTool.definition_hash()\` implementation and reports missing/extra identifiers.
5. Runs \`experiments/e1_protocol_runner.py\`.
6. Validates the output manifest against \`run_manifest.schema.json\`.
7. Uploads a ZIP containing raw input snapshots, the rebuilt merged registry, outputs and hashes.

Run locally after executing \`bash scripts/fetch_data.sh\`:

\`\`\`bash
python -m pip install -e ".[experiment]"
cp data/processed/registry_merged.json /tmp/registry_merged_committed.json
bash scripts/fetch_data.sh
python experiments/e1_protocol_runner.py \\
  --root . \\
  --output results/definitive/E1 \\
  --committed-merged /tmp/registry_merged_committed.json
\`\`\`

## Independent reference labels — mandatory gate

The repository's \`silver_labels.json\` and \`silver_labels_part*.jsonl\` are LLM-produced. They must not be used as the E1 reference population, even when they happen to reproduce an older number.

When no independent labels are supplied, the runner produces two separate, shuffled blank files:

- \`reference_effect_annotator_A.csv\`
- \`reference_effect_annotator_B.csv\`

The restricted join file is \`restricted_reference_mapping.csv\`. Keep it away from annotators until both files are frozen. Each annotation unit is bound to both \`tool_id\` and a full SHA-256 digest of the exact tool definition. This is necessary because the same server/name can occur in source registries with different definitions.

After independent annotation and adjudication, produce a JSON file of this shape:

\`\`\`json
{
  "schema_version": "1.0.0",
  "label_source": "independent_human_reference",
  "independent_of_silver_labels": true,
  "generated_by_model": false,
  "labels": [
    {
      "tool_id": "server::tool_name",
      "definition_hash": "<64 lowercase hexadecimal characters>",
      "non_read_only": true
    }
  ]
}
\`\`\`

It must cover every unique tool definition in the union of the two raw source registries. The runner validates exact key coverage; it does not accept name-only labels, partial label coverage or model-generated labels. Use the same independent label set to measure each view, but do not feed it into contract extraction or model fitting.

The original protocol does not prescribe the human effect-label adjudication form. The two-sheet intake is a transparent operational control added for this E1 reference measurement; record annotators, adjudication and rationale in the submitted label file's accompanying documentation.

## Status semantics

A successful GitHub Actions execution means the pipeline ran and the artifact was uploaded. It does **not** mean E1 passed its scientific gate.

The E1 run manifest remains \`failed\` while the independent reference-label metric is blocked or committed-source hash checks disagree. It becomes \`completed\` only when the complete independent reference labels are supplied and the committed registry matches the pinned raw rebuild.

All catalogue experiment statuses remain \`planned_not_run\` until the artifacts have been reviewed and accepted.


## Independent-label reconciliation

After both files are completed, reconcile them without showing the restricted map before annotation freeze:

\`\`\`bash
python experiments/e1/reconcile_reference_annotations.py \\
  --annotator-a reference_effect_annotator_A.csv \\
  --annotator-b reference_effect_annotator_B.csv \\
  --mapping restricted_reference_mapping.csv \\
  --output-dir e1_reference_reconciliation \\
  --annotator-a-id <ANNOTATOR_A_ID> \\
  --annotator-b-id <ANNOTATOR_B_ID>
\`\`\`

The utility checks exact annotation-unit coverage, tool-name consistency, full SHA-256 definition identities, boolean decisions, confidence and rationale. It writes raw Cohen's kappa, an agreement report, disagreements and an adjudication template. It does not automatically resolve disagreements. When any disagreement exists, the E1 reference-label JSON is withheld until an adjudicator completes the template and supplies a frozen adjudication rule:

\`\`\`bash
python experiments/e1/reconcile_reference_annotations.py \\
  --annotator-a reference_effect_annotator_A.csv \\
  --annotator-b reference_effect_annotator_B.csv \\
  --mapping restricted_reference_mapping.csv \\
  --output-dir e1_reference_reconciliation_final \\
  --annotator-a-id <ANNOTATOR_A_ID> \\
  --annotator-b-id <ANNOTATOR_B_ID> \\
  --adjudicated-csv adjudicated_labels.csv \\
  --adjudicator-id <ADJUDICATOR_ID> \\
  --adjudication-rule "<FROZEN_RULE>"
\`\`\`

The emitted \`reference_labels.json\` is accepted by the E1 runner's \`--reference-labels\` option only when the label set covers every unique source definition exactly. The metric must not be computed from partial coverage.
