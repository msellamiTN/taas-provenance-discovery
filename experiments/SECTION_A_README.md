# PaMCP Section A — local preflight

Standard-library-only, read-only preflight for E0–E2. It inventories repository state, checks protocol sections, detects registry/annotation inputs, and hashes historical E0–E2 outputs. It does not execute legacy experiments or promote old outputs to confirmatory evidence.

```bash
python -m pytest -q
python -m experiments.section_a --root /path/to/taas-provenance-discovery --output /path/to/new/campaign-section-a-preflight.json
```

The output path must not already exist. The runner never edits repository sources or historical result files.
