# E2 — Human annotation protocol (preparation only)

**Protocol source:** the supplied \`Experimental_Protocol_PaMCP.docx\` and \`PaMCP_Experimental_Spec_v1.0\`.

**Status:** \`prepared_not_run\`. This document does not change the experiment status.

## Objective and registered factors

E2 validates the semantic typing function used by PaMCP reachability.

| Factor | Levels |
|---|---|
| Typing evidence | schema only; schema + name/description; schema + probe output |
| Certainty threshold | 0.5; 0.7; 0.9 |
| Reference | Two independent human annotators |
| Comparator | Structural-only JSON-shape typing |

Report type precision, recall, F1, Cohen's kappa between the two annotators, and uncertain type share. Outputs: confusion matrix and F1/uncertainty versus threshold.

## Annotation unit

One row represents one type-bearing target: one input argument (\`target_role=input\`) or one tool return value (\`target_role=output, field_name=$return\`). The sheet includes the tool name and description, target field schema, and full input/output schema context. Missing output schemas remain missing evidence; annotators must not invent schemas.

## Human annotation fields

- \`type_kind\`: one of the repository's 16 semantic kinds: text, document, table, record, media, credential, identifier, location, number, url, path, query, code, datetime, boolean, none.
- \`type_domain\`: optional domain qualifier, e.g. \`review\`, \`stock\`, \`repo\`; leave blank when not justified.
- \`is_collection\`: whether the type is a collection (\`[]\`).
- \`is_uncertain\`: true when evidence is insufficient for a defensible type.
- \`confidence_0_1\`: annotator confidence in [0,1].
- \`rationale\`: concise evidence-based rationale.

\`none\` is a semantic type, not an uncertainty marker. For an unresolved type, set \`is_uncertain=true\`; do not silently map unknown values to \`text\` or \`none\`. The canonical type string is \`kind[:domain][[]]\`.

## Independence and leakage controls

1. Two annotators receive separate exports with the same target units and independently shuffled row order.
2. Annotators must not see each other's annotations, model predictions, silver LLM labels, or experiment outputs.
3. Freeze both annotation files before joining them with the restricted \`annotation_unit_id -> tool_id\` mapping.
4. Compute Cohen's kappa on unadjudicated labels and preserve disagreement/uncertainty counts.
5. Do not use \`data/llm_records/silver_labels*.jsonl\` or old LLM-generated type assignments as human gold.
6. If adjudication is introduced, freeze its rule and adjudicator before examining disagreements; report raw kappa before adjudication.

## Sampling is an explicit preregistration parameter

The supplied protocol does not specify E2 subset size, sampling seed, or sampling design. The preparation script therefore requires the operator to freeze \`sample_size\`, \`seed\`, \`sampling_design\` (\`simple_random\` or \`stratified_source_category\`), and the exact registry snapshot SHA-256 before annotation begins.

Example command shape only; placeholders are deliberately unresolved:

\`\`\`bash
python experiments/e2/prepare_annotation_tasks.py \\
  --registry data/processed/registry_merged.json \\
  --output artifacts/e2_annotation_round1 \\
  --sample-size <PREREGISTERED_N> \\
  --seed <PREREGISTERED_SEED> \\
  --sampling-design <simple_random|stratified_source_category>
\`\`\`

## Scoring contract to freeze before running E2

Before labels are collected, freeze the exact type-match rule (\`kind\`, \`domain\`, collection status), domain normalization, treatment of unresolved labels, abstention handling for precision/recall/F1, macro/micro averaging, target-tool bootstrap unit, and any adjudication procedure. For each evidence condition and threshold, report the type confusion matrix, precision, recall, F1, uncertainty share, and exact denominators. Do not tune thresholds on evaluation annotations.

The \`schema + probe output\` condition cannot run until E3 provides frozen credential-free, hash-bound probe traces for the same tools. Do not substitute LLM-generated outputs or fabricated examples.

## Completion gate

E2 remains \`prepared_not_run\` until the sample manifest, two independently completed annotation files, their hashes, the code commit, and frozen scoring rules are available and reviewed.
