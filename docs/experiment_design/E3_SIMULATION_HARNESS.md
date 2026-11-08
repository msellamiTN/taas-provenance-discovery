# E3 synthetic fixture harness — operational status

**Status:** software-validation aid only. This does not release E3 and does not replace
credential-free runnable reference servers, isolated probes, observed traces, or
independent effect annotation required by `E3_EFFECT_REFERENCE_PROTOCOL.md`.

## Run

```bash
python experiments/e3_simulation.py --output artifacts/e3_simulation
pytest -q tests/test_e3_simulation.py
```

The harness creates 12 deterministic synthetic event fixtures covering the eight
effect labels and selected multi-label cases. It checks that the fixture adapter
maps the event vocabulary to the fixture's expected labels and exports:

- `e3_simulated_trace_fixtures.csv` — event fixture records and exact-match checks;
- `e3_synthetic_fixture_coverage.svg` — number of fixture cases containing each label;
- `e3_simulation_manifest.json` — explicit evidence classification, limitations and hashes.

## Interpretation restrictions

- `synthetic_fixture` is not a tool invocation, observation, or reference label.
- No MCP server, process, filesystem, database, network destination, payment system,
  or access-control system is invoked or observed.
- The chart is fixture coverage, **not** precision, recall, F1, probe coverage, or
  empirical effect prevalence.
- Do not merge these artifacts into `results/definitive/E3`, paper result tables,
  confidence intervals, or hypothesis tests.
- The E3 release gate remains blocked until actual hash-bound probe traces and
  independent/adjudicated effect labels are collected under the approved protocol.

## Next real-evidence dependency

Obtain a credential-free reference-server inventory and a genuinely isolated,
disposable execution environment. Until then, use this harness only for deterministic
software regression and output-format validation.
