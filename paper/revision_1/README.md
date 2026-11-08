# PaMCP — Revision 1 (TSC reviewer-driven)

This directory is an additive revision package on branch \`research/pamcp-final-evaluation\`.
The original manuscript, E1–E22 scripts, raw records and reported results are deliberately preserved.

## What this revision changes

1. Reclassifies every empirical claim by evidence source and removes the interpretation that the current zero-exposure result independently validates a verifier.
2. Adds an explicit audit of the \(J_A/J_B\) unsafe-set containment that makes the simulated zero false-admission result construction-dependent.
3. Replaces E14's task-level class shortcut with a scope-aware re-analysis that reports **violation**, **indeterminate**, and **permitted** outcomes separately.
4. Audits the actual manifest sanitizer and tests a server-side alias-manifest prototype. It does not assume that all provider-controlled names are removed.
5. Recomputes the E14 comparison at the task level, with attacks nested within tasks. The re-analysis is explicitly exploratory because the estimand differs from the original confirmatory F5.
6. Provides scope-policy unit tests and a revised evaluation-section draft that states negative and inconclusive findings directly.
7. Defines the new evidence needed for human ground truth, real MCP execution, task success, QoS and experience reuse.

## Folder map

- \`paper/revision_1/REVIEW_RESPONSE.md\`: point-by-point response to the reviewer comments.
- \`paper/revision_1/EVIDENCE_LEDGER.md\`: current result interpretation and claim restrictions.
- \`paper/revision_1/EXPERIMENT_PROTOCOL.md\`: revised X1–X8 protocol, metrics, controls and completion gates.
- \`paper/revision_1/evaluation_revision.tex\`: conservative replacement-section draft using only currently reported numbers.
- \`experiments/revision_1/audit_label_overlap.py\`: computes the \(J_A/J_B\) overlap directly from the committed records.
- \`experiments/revision_1/scope_policy.py\`: strict task-effect parsing and scope classification.
- \`experiments/revision_1/reanalyse_e14_scope_aware.py\`: re-analyses saved E18 toolkits with all attack classes and explicit scope uncertainty.
- \`experiments/revision_1/audit_sanitiser.py\`: tests the actual sanitizer and an alias-based manifest prototype.
- \`experiments/revision_1/test_scope_policy.py\`: deterministic tests for scope semantics.

## Reproduction

From the repository root, in an environment with the project dependencies installed:

\`\`\`bash
python -m pytest experiments/revision_1/test_scope_policy.py
python experiments/revision_1/audit_label_overlap.py
python experiments/revision_1/audit_sanitiser.py
python experiments/revision_1/reanalyse_e14_scope_aware.py
\`\`\`

All new outputs are written under \`results/revision_1/\`; the scripts do not overwrite \`results/final/\`.

## Important status

The revision corrects analysis code and claim scope. It does **not** claim to have collected human annotations, executed third-party MCP servers, performed end-to-end task runs, measured production QoS, or evaluated experience reuse. Those experiments require external data/servers and are explicitly listed as pending in the protocol. No synthetic or simulated observation is relabelled as a runtime measurement.

The new scripts have been source-reviewed but must be run in the repository's Python environment before their generated JSON is treated as a result.