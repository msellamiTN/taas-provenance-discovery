# E3 tri-state declared-hint correction

## Why this correction is required

The previous E3 scorer treated every prediction other than the boolean value `True` as a negative. That included `None`, which represents a missing `readOnlyHint`. The same rows were also counted in the `unknown` field. Consequently, missing hints were double-represented as false negatives or true negatives and as unknowns.

This is not a valid confusion matrix. An absent MCP hint is not a declaration that a tool is read-only.

## Corrected semantics

- `readOnlyHint=false` predicts a state-changing effect (`true`).
- `readOnlyHint=true` predicts no state-changing effect (`false`).
- Missing `readOnlyHint` predicts `None` (unknown), not `false`.

The corrected scorer reports the TP/FP/FN/TN confusion matrix only over covered records. It separately reports:

- total and evaluated records;
- overall hint coverage;
- the number of reference-unsafe and reference-safe tools among unknown records;
- the fraction of all reference-unsafe tools for which a hint is present (`unsafe_reference_coverage`);
- unsafe captures divided by all reference-unsafe tools (`unsafe_capture_rate_all`).

Precision, recall and mismatch rate are conditional on covered records. They must not be read as registry-wide metrics. The all-registry unsafe capture rate is provided separately.

## Expected consistency check for the current frozen labels

The current E1/E3 registry snapshot has 569 tools, 44 tools with `readOnlyHint=true`, and 525 without a hint. Under reference labels B, 120 tools are unsafe. One of the 44 covered tools is unsafe, leaving:

| Quantity | Expected count |
|---|---:|
| Covered | 44 |
| Unknown | 525 |
| Covered unsafe | 1 |
| Covered safe | 43 |
| Unknown unsafe | 119 |
| Unknown safe | 406 |

For the declared-hint confusion matrix, the expected covered-only values are TP=0, FP=0, FN=1, TN=43. Coverage is 44/569 (7.73%). Unsafe reference coverage is 1/120 (0.83%); unsafe capture across the full reference-unsafe population is 0/120. These checks are derived from the already committed E1 registry and labels B; this correction does not create new labels or observations.

## Historical output preservation

The previous E3 result is preserved byte-for-byte at:

`results/history/E3_effects_pre_tristate_20261108.json`

Its original Git blob SHA is `92308ad9b3df104bec91af8944189aced903cc9e`.

The latest base branch also contains a later `results/final/E3_effects.json` run
(`E3_effects-2026-11-08T06:43:50Z-12b5336ee5`). That result already applies the essential
missingness rule: TP=0, FP=0, FN=1, TN=43, 525 unknown hints, and 119 unknown tools unsafe under
labels B. Its manifest, however, records dirty code files and its older schema does not explicitly
report total/evaluated counts, overall coverage, unknown-safe composition, unsafe-reference coverage,
or unsafe capture over the full reference-unsafe population. This patch leaves that file unchanged
and writes the expanded, hash-pinned output separately as `E3_effects_tristate.json`.

The corrected standalone runner uses only the already committed merged registry and label files, and does not require the absent raw MCPToolBench++ JSON package:

```bash
python experiments/final/run_e3_tristate_only.py
python experiments/final/tables_final.py
```

It writes `results/final/E3_effects_tristate.json` with hashes for the registry, labels A and all three labels-B shards. It refuses to overwrite an existing corrected result unless `--replace` is passed. The full E1/E2/E3 runner also writes the corrected, versioned E3 result and now hashes the label inputs for E1, E2 and E3.

After the rerun, record the new run commit, Python version, input hashes and result-file SHA. Do not substitute the expected consistency counts above for an actual execution.

## E11 scope correction

The E11 runner currently uses only `reviews_registry()`, the review scenario's own 11-tool registry. It does not append the public 569-tool registry. The misleading source comment has been corrected. Existing E11 results therefore remain scenario-local; a combined-registry E11 analysis would be a separately defined and executed experiment.
