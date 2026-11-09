"""Compare a reproduction run with the reference results reported in the paper.

    python experiments/final/compare_results.py results/reproduced

Every numeric, boolean and string leaf of each result file is compared with the same leaf in results/final,
except the manifest (run id, commit, hashes, versions) and wall-clock measurements (keys ending in _ms, _s,
_mb and their percentiles), which depend on the machine. A leaf is identical, close (relative difference at
most 1e-6, or absolute at most 1e-9), or different. Files that run_all.py copied from the reference (because
their series was not re-run) are skipped. Writes comparison.json and comparison.md into the run directory.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "results" / "final"
TIMING = re.compile(r"(_ms|_s|_mb|_ms_p50|_ms_p95|_ms_max|_ms_mean|seconds|_time|time_s)$")
SKIP_KEYS = {"manifest", "human_sheet", "path", "created", "run_id"}


def leaves(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            if k in SKIP_KEYS or TIMING.search(str(k)):
                continue
            yield from leaves(v, f"{path}/{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from leaves(v, f"{path}[{i}]")
    else:
        yield path, x


def same(a, b) -> str:
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str) or a is None or b is None:
        return "identical" if a == b else "different"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b or (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b)):
            return "identical"
        if abs(a - b) <= 1e-9 or abs(a - b) <= 1e-6 * max(abs(a), abs(b)):
            return "close"
        return "different"
    return "identical" if a == b else "different"


def compare(run: Path, reference: Path | None = None) -> dict:
    reference = reference or REFERENCE
    copied = set()
    log = run / "run_log.json"
    if log.exists():
        for rec in json.load(open(log)):
            copied |= set(rec.get("copied_from_reference", []))
    out = {}
    for p in sorted(run.glob("*.json")):
        name = p.stem
        if name in ("run_log", "comparison") or name in copied:
            continue
        ref = reference / p.name
        if not ref.exists():
            out[name] = {"status": "no reference file"}
            continue
        A = dict(leaves(json.load(open(ref))))
        B = dict(leaves(json.load(open(p))))
        keys = sorted(set(A) | set(B))
        counts = {"identical": 0, "close": 0, "different": 0, "missing": 0}
        diffs = []
        for k in keys:
            if k not in A or k not in B:
                counts["missing"] += 1
                diffs.append((k, A.get(k, "<absent>"), B.get(k, "<absent>"), float("inf")))
                continue
            s = same(A[k], B[k])
            counts[s] += 1
            if s == "different":
                try:
                    d = abs(float(A[k]) - float(B[k]))
                except (TypeError, ValueError):
                    d = float("inf")
                diffs.append((k, A[k], B[k], d))
        diffs.sort(key=lambda x: -x[3] if x[3] != float("inf") else -1e300)
        status = "identical" if counts["different"] == counts["missing"] == 0 and counts["close"] == 0 else \
            "identical up to rounding" if counts["different"] == counts["missing"] == 0 else "differs"
        out[name] = {"status": status, "leaves": len(keys), **counts,
                     "examples": [{"path": k, "reference": a, "reproduced": b} for k, a, b, _ in diffs[:8]]}
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run = Path(args[0] if args else "results/reproduced")
    run = run if run.is_absolute() else ROOT / run
    ref = None
    if "--reference" in sys.argv:       # e.g. --reference results/revision_2 for the Revision 2 series
        ref = Path(sys.argv[sys.argv.index("--reference") + 1])
        ref = ref if ref.is_absolute() else ROOT / ref
        args = [a for a in args if Path(a) != ref and a != sys.argv[sys.argv.index("--reference") + 1]]
        run = Path(args[0] if args else "results/reproduced")
        run = run if run.is_absolute() else ROOT / run
    res = compare(run, ref)
    json.dump(res, open(run / "comparison.json", "w"), indent=1, default=str)
    md = ["| Result file | Status | Leaves compared | Identical | Close | Different | Missing |",
          "|---|---|---|---|---|---|---|"]
    for n, v in res.items():
        if "leaves" in v:
            md.append(f"| {n} | {v['status']} | {v['leaves']} | {v['identical']} | {v['close']} | {v['different']} | "
                      f"{v['missing']} |")
        else:
            md.append(f"| {n} | {v['status']} | | | | | |")
    for n, v in res.items():
        if v.get("examples"):
            md.append(f"\n**{n}**, first differences:\n")
            md += [f"* `{e['path']}`: reference {e['reference']!r}, reproduced {e['reproduced']!r}" for e in v["examples"]]
    (run / "comparison.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
