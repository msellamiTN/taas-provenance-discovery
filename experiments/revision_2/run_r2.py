"""Single entry point for the Revision 2 analyses (TSC revision), the revised Section 8 figures and tables.

Every step writes into a separate output directory (default results/reproduced_r2) so that the committed reference
results (results/revision_2) are never overwritten; compare the two with
    python experiments/final/compare_results.py results/reproduced_r2 --reference results/revision_2

Usage
    python experiments/revision_2/run_r2.py --list
    python experiments/revision_2/run_r2.py                       # default steps (all except probe and the long scale run)
    python experiments/revision_2/run_r2.py --only label_swap,family
    python experiments/revision_2/run_r2.py --all                 # also x7 (about 1.5 h) and the server probe
    python experiments/revision_2/run_r2.py --quick-x7            # x7 with small registries only (minutes)
    python experiments/revision_2/run_r2.py --out results/my_run

LLM outputs (analyst goals, labels, calibration answers) are replayed from data/llm_records; no API key is needed.
The probe step starts the six MCP reference servers with npx / uvx under strace and therefore needs Node.js >= 18,
uv, strace and network access to the npm and PyPI registries; its records go to <out>/x2_probe, not data/x2_probe.
Live servers change between versions, so probe results are not expected to be identical to the reference.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "experiments" / "revision_2"
REF = ROOT / "results" / "revision_2"
PY = sys.executable

# name: (command, inputs needed from earlier steps (R2 result stems), approx. minutes on 2 vCPU, default?)
STEPS = {
    "label_swap": ([R2 / "r2_label_swap.py"], [], 2, True),
    "evaluator_audit": ([R2 / "r2_evaluator_audit.py"], [], 2, True),
    "x3_dev": ([R2 / "r2_x3_retrieval.py", "dev"], [], 10, True),
    "v2_select": ([R2 / "r2_v2_select.py"], [], 3, True),
    "x3_test": ([R2 / "r2_x3_retrieval.py", "test"], ["R2_X3_dev"], 25, True),
    "v2_eval": ([R2 / "r2_v2_eval.py"], [], 5, True),
    "family": ([R2 / "r2_family.py"], ["R2_X3_test", "R2_v2_eval"], 1, True),
    "x6_x13": ([R2 / "r2_x6_x13_composition.py"], [], 4, True),
    "reuse": ([R2 / "r2_e21_reuse.py"], [], 5, True),
    "calibration": ([R2 / "r2_x2_calibration_score.py"], [], 1, True),
    "x7": ([R2 / "r2_x7_scale.py"], [], 90, False),
    "probe": ([R2 / "r2_x2_probe.py", "inventory"], [], 5, False),
    "probe_run": ([R2 / "r2_x2_probe.py", "probe", "--workers", "3"], [], 3, False),
    "probe_analyse": ([R2 / "r2_x2_analyse.py"], [], 1, False),
    "figures": ([ROOT / "paper" / "make_eval_r2.py"], [], 2, True),
}


def copy_needed(out: Path, stems: list[str]) -> list[str]:
    """Copy reference outputs a step depends on when the producing step was not run in this output directory."""
    copied = []
    for s in stems:
        if not (out / f"{s}.json").exists():
            shutil.copy2(REF / f"{s}.json", out / f"{s}.json")
            copied.append(s)
        raw = REF / "raw" / f"{s}.jsonl.gz"
        if raw.exists() and not (out / "raw" / raw.name).exists():
            (out / "raw").mkdir(parents=True, exist_ok=True)
            shutil.copy2(raw, out / "raw" / raw.name)
    return copied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/reproduced_r2")
    ap.add_argument("--only", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quick-x7", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, (cmd, need, mins, dflt) in STEPS.items():
            print(f"{k:16s} ~{mins:3d} min  {'default' if dflt else 'optional'}  "
                  f"{' '.join(str(c).replace(str(ROOT) + '/', '') for c in cmd)}"
                  + (f"   (needs {', '.join(need)})" if need else ""))
        return
    out = Path(a.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    sel = [s for s in a.only.split(",") if s] or [k for k, v in STEPS.items() if v[3] or a.all]
    if a.quick_x7 and "x7" not in sel:
        sel.append("x7")
    unknown = [s for s in sel if s not in STEPS]
    if unknown:
        sys.exit(f"unknown steps: {unknown}; see --list")
    env = {**os.environ, "PYTHONHASHSEED": "0", "MPLBACKEND": "Agg", "PAMCP_RESULTS_DIR": str(out),
           "PAMCP_PROBE_RECORDS": str(out / "x2_probe"), "PAMCP_R2_RESULTS": str(out),
           "PAMCP_PAPER_OUT": str(out / "paper"), "PYTHONPATH": str(ROOT / "src")}
    log_p = out / "run_log.json"
    log = json.loads(log_p.read_text()) if log_p.exists() else []
    order = [k for k in STEPS if k in sel]
    for k in order:
        cmd, need, mins, _ = STEPS[k]
        argv = [PY] + [str(c) for c in cmd] + (["--quick"] if k == "x7" and a.quick_x7 else [])
        copied = copy_needed(out, need)
        if k == "figures":
            # figures read every Revision 2 result: fill gaps with the reference so that a partial run still renders
            copied += copy_needed(out, [p.stem for p in REF.glob("R2_*.json")])
        t0 = time.time()
        print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {k}: {' '.join(argv[1:])}", flush=True)
        r = subprocess.run(argv, cwd=ROOT, env=env)
        rec = {"step": k, "argv": argv[1:], "returncode": r.returncode, "seconds": round(time.time() - t0, 1),
               "copied_from_reference": copied, "finished": datetime.now(timezone.utc).isoformat()}
        log.append(rec)
        log_p.write_text(json.dumps(log, indent=1))
        if r.returncode != 0:
            print(f"step {k} failed (exit {r.returncode}); see the output above", flush=True)
    print(f"done; results in {out}. Compare: python experiments/final/compare_results.py "
          f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out} --reference results/revision_2")


if __name__ == "__main__":
    main()
