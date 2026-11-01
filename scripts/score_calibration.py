"""Score the ρ_LLM calibration answers and build measured model profiles (Definition 6, rule 2).

Correctness: exact classes (sum, count) need the exact integer; classify needs the majority label;
extract needs the city name. Produces data/processed/profile_<model>.json and a per-cell table.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from taas.model_profile import DEFAULT_PRIORS, ModelProfile  # noqa: E402


def correct(ans, gold) -> bool:
    a = str(ans).strip().lower()
    g = gold["answer"]
    if isinstance(g, int):
        m = re.search(r"-?\d[\d,]*", a)
        return bool(m) and int(m.group(0).replace(",", "")) == g
    return str(g).lower() in a


def main(gold_path: str) -> None:
    gold = json.load(open(gold_path))
    index = {d["id"]: d for d in json.load(open(ROOT / "data/calibration/index.json"))}
    # the gold file is committed only after scoring so that no LLM run could read it
    (ROOT / "data/calibration/gold.json").write_text(json.dumps(gold, indent=1))
    table = {}
    for model in ("haiku", "sonnet"):
        p = ROOT / f"data/llm_records/calibration_answers_{model}.json"
        if not p.exists():
            continue
        ans = json.load(open(p))
        recs = []
        for iid, it in index.items():
            recs.append({"class": it["class"], "n": it["n"], "correct": correct(ans.get(iid, ""), gold[iid]),
                         "answer": ans.get(iid), "gold": gold[iid]["answer"]})
        prof = ModelProfile.from_calibration(f"claude-{model}", [r for r in recs], tau=0.9, priors=DEFAULT_PRIORS)
        json.dump(prof.to_json(), open(ROOT / f"data/processed/profile_{model}.json", "w"), indent=1)
        json.dump(recs, open(ROOT / f"results/calibration_{model}.json", "w"), indent=1)
        cells = {}
        for r in recs:
            cells.setdefault(r["class"], {}).setdefault(r["n"], []).append(r["correct"])
        table[model] = {c: {n: sum(v) / len(v) for n, v in sorted(d.items())} for c, d in cells.items()}
    (ROOT / "results").mkdir(exist_ok=True)
    json.dump(table, open(ROOT / "results/calibration_table.json", "w"), indent=1)
    for m, t in table.items():
        print(m)
        for c, d in t.items():
            print(f"  {c:14s} " + "  ".join(f"n={n}:{v:.2f}" for n, v in d.items()))


if __name__ == "__main__":
    main(sys.argv[1])
