"""Check every number in sections/evaluation_final*.tex and tables_final/*.tex against results/final/*.json.

A printed number matches if some value in the result files (or a derived value listed below), as a fraction or
as a percentage, rounds to it at the printed precision. Unmatched numbers are listed for manual review;
design constants and cross-references are whitelisted. Run: python3 paper/check_numbers_final.py
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "final"
vals: set[float] = set()


def walk(x):
    if isinstance(x, bool):
        return
    if isinstance(x, (int, float)):
        vals.add(float(x))
        if 1.0 < x < 2.0:          # cost ratios printed as a relative excess (1.157 -> 15.7%)
            vals.add(float(x) - 1.0)
        if x > 1.0:                # milliseconds printed in seconds
            vals.add(float(x) / 1000.0)
    elif isinstance(x, dict):
        for k, v in x.items():
            if k == "manifest":
                continue
            walk(v)
            try:
                vals.add(float(k))
            except ValueError:
                for part in re.findall(r"\d+(?:\.\d+)?", k):
                    vals.add(float(part))
    elif isinstance(x, list):
        for v in x:
            walk(v)


for p in sorted(RES.glob("*.json")):
    walk(json.load(open(p)))


def raw(name):
    with gzip.open(RES / "raw" / f"{name}.jsonl.gz", "rt") as fh:
        return [json.loads(line) for line in fh]


# derived quantities stated in the text: E10 per-check pass rates and differences
agg = defaultdict(lambda: defaultdict(list))
for r in raw("E10_validity"):
    for c in "SCELVM":
        agg[r["method"]][c].append(bool(r[c]))
rates = {m: {c: sum(v) / len(v) for c, v in d.items()} for m, d in agg.items()}
for d in rates.values():
    vals.update(d.values())
    vals.update(1 - x for x in d.values())
s10 = json.load(open(RES / "E10_validity.json"))["summary"]
for k, v in s10.items():
    if k.endswith("eligible-only"):
        u = s10[k.replace("eligible-only", "unfiltered")]
        vals.add(v["joint_feasible"] - u["joint_feasible"])

WHITELIST = {
    # design constants, sizes and identifiers stated by the protocol or the paper
    "0.05", "0.5", "0.4", "0.6", "0.7", "0.75", "0.8", "0.9", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "12", "13", "16", "17", "18", "19", "20", "21", "22", "40", "60", "95", "100", "128", "2^3", "1,000", "10",
}
CONTEXT_SKIP = re.compile(r"(Section|Table|Fig\.|Figs\.|Eq\.|Eqs\.|Algorithm|Algorithms|Proposition|Property|"
                          r"Observation|E|F|RQ|\\chi_|chi)~?$")


def numbers(tex: str):
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    tex = re.sub(r"\\(label|ref|input|cite|includegraphics|url|footnote)\{[^}]*\}", "", tex)
    tex = tex.replace("{,}", ",").replace("\\,", " ")
    for m in re.finditer(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)", tex):
        before = tex[max(0, m.start() - 12):m.start()]
        yield m.group(1), before, tex[max(0, m.start() - 40):m.end() + 20].replace("\n", " ")


def matches(s: str) -> bool:
    x = float(s.replace(",", ""))
    d = len(s.split(".")[1]) if "." in s else 0
    tol = 0.5 * 10 ** -d + 1e-9
    for v in vals:
        for cand in (v, 100 * v, abs(v), 100 * abs(v), 1000 * v):
            if abs(cand - x) <= tol:
                return True
    return False


files = sorted((ROOT / "paper" / "sections").glob("evaluation_final*.tex")) + \
    sorted((ROOT / "paper" / "tables_final").glob("*.tex"))
bad = 0
for f in files:
    for s, before, ctx in numbers(f.read_text()):
        if CONTEXT_SKIP.search(before.rstrip("{(~ ")) or s in WHITELIST:
            continue
        if not matches(s):
            bad += 1
            print(f"{f.name}: {s:>8}  …{ctx}…")
print(f"{bad} unmatched numbers (review each by hand)")
sys.exit(0)
