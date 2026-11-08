# Revision 1 experiment scripts

These scripts are designed to run from the repository root and keep their outputs separate from \`results/final/\`.

## Commands

\`\`\`bash
python -m pytest experiments/revision_1/test_scope_policy.py
python experiments/revision_1/audit_label_overlap.py
python experiments/revision_1/audit_sanitiser.py
python experiments/revision_1/reanalyse_e14_scope_aware.py
\`\`\`

Set \`PAMCP_REVISION_RESULTS\` to override the output folder. Default: \`results/revision_1/\`.

## Script semantics

- \`audit_label_overlap.py\` computes the binary unsafe-set relationship and Cohen's \(\kappa\) from the two committed machine-label sources. It does not create human ground truth.
- \`scope_policy.py\` distinguishes explicit task scope from missing scope. Class-only \`write\`, \`delete\` or \`egress\` requirements are ambiguous, not global permission.
- \`reanalyse_e14_scope_aware.py\` reads the committed E18 toolkit records, evaluates all five attack classes for every task/method, and returns definite violations separately from indeterminate scope cases. It re-aggregates to one task-level value before the paired comparison. It uses \(J_B\), which is still an LLM label set.
- \`audit_sanitiser.py\` scans real outputs from the current \`sanitise()\` and compares them with a prototype alias manifest. It is a unit-level manifest transformation test, not an agent-context or execution benchmark.

## Interpretation guardrails

No output from these scripts may be described as human-validated or runtime-observed. The scope-aware E14 re-analysis is exploratory (not a replacement confirmatory test with inherited F5 status). The alias manifest is a prototype and is not integrated into the runtime MCP client in this revision.