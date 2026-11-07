# E1 annotation intake validator

This utility validates the two independently completed E1 annotation sheets against
the approved annotation contract. It is an intake/quality-control tool, not an
adjudicator and not an experiment result generator.

## Run

```bash
python -m taas.e1_annotation_intake annotator_A.csv annotator_B.csv \
  --json-out e1_intake_report.json \
  --disagreements-out e1_disagreements.csv
```

The command checks required columns, non-empty unique unit IDs, strict binary labels,
allowed effect classes, finite confidence in [0,1], rationale presence, matching unit
sets, and consistent tool-name context. It reports raw agreement, Cohen's kappa,
marginal counts, and disagreement rows.

A kappa value of `null` is reported when expected agreement is one (degenerate
marginals); raw agreement and category counts remain available. The tool never
changes either input sheet and never adjudicates disagreements. Do not calculate
agreement until both source sheets have been independently completed and frozen.

## Important limitations

- This validator does not establish that annotations are semantically correct.
- It does not verify definition hashes because the owner-only crosswalk is intentionally
  kept outside the annotator packets. A separate owner-side identity/hash audit is
  required before E1 is frozen.
- It does not support unresolved labels; insufficient evidence must be escalated
  under the approved guide before sheet freeze.
