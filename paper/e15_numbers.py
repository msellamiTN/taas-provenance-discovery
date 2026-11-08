"""Print the E15 quantities used in sections/evaluation_final_e15.tex (from results/final/E15_scalability.json
and its raw records), so that the paragraph can be checked against them."""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
R = json.load(open(ROOT / "results" / "final" / "E15_scalability.json"))
with gzip.open(ROOT / "results" / "final" / "raw" / "E15_scalability.jsonl.gz", "rt") as fh:
    raw = [json.loads(line) for line in fh]

print("config", R["manifest"].get("config"))
for n, v in R["results"].items():
    print(n, {k: round(x, 3) if isinstance(x, float) else x for k, x in v.items()})
rows = [r for r in raw if "n" in r and "error" not in r]
for n in sorted({r["n"] for r in rows}):
    sel = [r for r in rows if r["n"] == n]
    rest = [1000 * (r["total_s"] - r["retrieval_s"] - r["eligibility_s"]) for r in sel]
    print(n, "tasks", len(sel), "abstain", sum(r["abstain"] for r in sel),
          "chi", dict(Counter(r["chi"] for r in sel if r["chi"])), "regime", dict(Counter(r["regime"] for r in sel)),
          "eligible p50", np.median([r["eligible"] for r in sel]),
          "total-retrieval-eligibility p50 ms", round(float(np.median(rest)), 1),
          "max total ms", round(1000 * max(r["total_s"] for r in sel), 1))
errs = [r for r in raw if "error" in r]
print("errors", len(errs), errs[:2])
for g, v in R["optimality_gap"].items():
    print("gap", g, {k: round(x, 3) if isinstance(x, float) else x for k, x in v.items()})
gaps = [r["optimality"] for r in raw if "optimality" in r]
print("exact regimes", Counter((g["goals"], g["exact_regime"]) for g in gaps))
