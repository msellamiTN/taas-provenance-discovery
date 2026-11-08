"""Run the final PaMCP evaluation (protocol E1-E22) in one place.

    python experiments/final/run_all.py --list
    python experiments/final/run_all.py --out results/reproduced --only E4-E7,E11-E12
    python experiments/final/run_all.py --out results/reproduced --all --e15-max-n 10000

Every series writes its result files (JSON with a manifest, raw per-item records) to --out, never to the
reference results in results/final unless --out results/final is given explicitly. After a run,
experiments/final/compare_results.py compares --out with results/final.

No API key is needed: every LLM output (analyst goal contracts, the two labellings, MCP-Zero requests and
server summaries, COLT training queries, ToolScope equivalence judgements, calibration answers) was recorded
once and is replayed from data/llm_records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "experiments" / "final"
REFERENCE = ROOT / "results" / "final"

PP_REPO = "https://github.com/mcp-tool-bench/MCPToolBenchPP.git"
PP_COMMIT = "2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037"
PP_CATEGORIES = ("browser", "file_system", "finance", "map", "pay", "search")

# name -> (description, commands, result files written, minutes on two vCPUs [reference machine])
STEPS: dict[str, tuple[str, list[list[str]], list[str], str]] = {
    "data": ("Fetch the six MCPToolBench++ request files (pinned commit; needed by E1 only)",
             [], [], "<1"),
    "E1-E3": ("Registry characterisation, typing agreement, declared and lexical effects",
              [["e01_e03_registry_typing_effects.py"]], ["E1_registry", "E2_typing", "E3_effects"], "~1"),
    "E4-E7": ("Exposure under policy encodings, forged metadata, imperfect verifier, trust policy",
              [["e04_e07_exposure.py"], ["e04_admitted.py"]],
              ["E4_exposure", "E5_forgery", "E6_verifier", "E7_trust", "E4_admitted"], "~25"),
    "E8": ("Single-tool retrieval (300-query sample, distractor curve) and its diagnosis",
           [["e08_single_tool.py"], ["e08_diagnostic.py"]], ["E8_single_tool", "E8_diagnostic"], "~15"),
    "E9-E10": ("Multi-tool set retrieval and set validity (independent evaluator)",
               [["e09_e10_sets.py"]], ["E9_sets", "E10_validity"], "~10"),
    "E11-E12": ("Capability gap on the review scenario; model-profile calibration",
                [["e11_e12_profile.py"]], ["E11_gap", "E12_profile"], "~1"),
    "E14-E18": ("Prompt-injection reachability and the 2^3 mechanism ablation",
                [["e14_e18_factorial.py"]], ["E14_injection", "E18_factorial"], "~15"),
    "E16": ("Registry and model evolution (152 events, rug pulls, cache invalidation)",
            [["e15_e16_scale_evolution.py", "--e16-only"]], ["E16_evolution"], "~3"),
    "E15": ("Cost and scalability on cloned registries; greedy vs exact optimality gap",
            [["e15_e16_scale_evolution.py", "--e15-only"]], ["E15_optimality_gap", "E15_scalability"],
            "~10 (to 10^4) / ~50 (to 10^5)"),
    "E17-E20": ("Counterexample-guided refinement; cost-weight and utility-floor sensitivity",
                [["e17_e20_refine_sensitivity.py"]], ["E17_refinement", "E20_sensitivity"], "~10"),
    "E22": ("Preregistered confirmatory family F1-F7 (Holm), resampling unit, split stability",
            [["e22_statistics.py"]], ["E22_statistics"], "~2"),
    "report": ("Markdown tables, figures, the paper's LaTeX tables",
               [["tables_final.py"], ["plots_final.py"], ["paper_figures_final.py"],
                [str(ROOT / "paper" / "make_tables_final.py")]], [], "~1"),
}
ORDER = list(STEPS)
# inputs a step reads from the results directory (copied from the reference results when absent, and logged)
NEEDS = {"E22": ["E4_exposure", "E8_single_tool", "E9_sets", "E10_validity", "E14_injection", "E18_factorial"],
         "report": [f for k in ORDER for f in STEPS[k][2]]}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fetch_mcptoolbenchpp(log) -> None:
    """Copy the six request files of MCPToolBench++ at the pinned commit into data/raw/mcptoolbenchpp and check
    them against the hashes recorded by the reference E1 run."""
    dst = ROOT / "data" / "raw" / "mcptoolbenchpp"
    dst.mkdir(parents=True, exist_ok=True)
    expected = json.load(open(REFERENCE / "E1_registry.json"))["results"]["raw_inputs"]
    have = {p.name: sha256(p) for p in dst.glob("*.json")}
    if have == expected:
        log("data: MCPToolBench++ request files present, hashes match the reference run")
        return
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "clone", "-q", PP_REPO, tmp + "/pp"], check=True)
        subprocess.run(["git", "-C", tmp + "/pp", "checkout", "-q", PP_COMMIT], check=True)
        for c in PP_CATEGORIES:
            cands = [p for p in sorted(Path(tmp, "pp", "data", c).glob("*.json"))
                     if "demo" not in p.name and "forqwen" not in p.name]
            shutil.copy(cands[0], dst / f"{c}.json")
    have = {p.name: sha256(p) for p in dst.glob("*.json")}
    bad = sorted(k for k in expected if have.get(k) != expected[k])
    log("data: fetched; hashes " + ("match the reference run" if not bad else f"DIFFER for {bad}"))


def fill_from_reference(out: Path, names: list[str], log) -> list[str]:
    copied = []
    for n in names:
        if not (out / f"{n}.json").exists() and (REFERENCE / f"{n}.json").exists():
            shutil.copy(REFERENCE / f"{n}.json", out / f"{n}.json")
            src = REFERENCE / "raw" / f"{n}.jsonl.gz"
            if src.exists():
                (out / "raw").mkdir(exist_ok=True)
                shutil.copy(src, out / "raw" / src.name)
            copied.append(n)
    if copied:
        log(f"  copied from the reference results (not re-run): {', '.join(copied)}")
    return copied


def run_step(name: str, out: Path, extra: list[str], log) -> dict:
    desc, cmds, _, _ = STEPS[name]
    t0 = time.time()
    rec = {"step": name, "description": desc, "commands": [], "status": "ok", "copied_from_reference": []}
    if name == "data":
        try:
            fetch_mcptoolbenchpp(log)
        except Exception as e:  # network or git failure: E1 cannot run, the rest can
            rec["status"] = f"failed: {e!r}"
            log(f"data: {rec['status']}")
        rec["seconds"] = round(time.time() - t0, 1)
        return rec
    if name in NEEDS:
        rec["copied_from_reference"] = fill_from_reference(out, NEEDS[name], log)
    env = dict(os.environ, PAMCP_RESULTS_DIR=str(out), PYTHONHASHSEED="0", MPLBACKEND="Agg")
    (out / "logs").mkdir(parents=True, exist_ok=True)
    for cmd in cmds:
        script = cmd[0] if os.path.isabs(cmd[0]) else str(HERE / cmd[0])
        args = cmd[1:] + (extra if cmd[0].startswith("e15_e16") else [])
        full = [sys.executable, script] + args
        rec["commands"].append(" ".join([Path(script).name] + args))
        logf = out / "logs" / f"{name}__{Path(script).stem}.log"
        t1 = time.time()
        with open(logf, "w") as fh:
            r = subprocess.run(full, cwd=str(HERE), env=env, stdout=fh, stderr=subprocess.STDOUT)
        log(f"  {Path(script).name} {' '.join(args)}: exit {r.returncode}, {time.time() - t1:.0f} s "
            f"(log: {logf.relative_to(out)})")
        if r.returncode != 0:
            rec["status"] = f"failed (exit {r.returncode}, see {logf.relative_to(out)})"
            tail = logf.read_text().strip().splitlines()[-15:]
            log("    " + "\n    ".join(tail))
            break
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="results/reproduced", help="results directory (default results/reproduced)")
    ap.add_argument("--only", default="", help="comma-separated steps, e.g. E4-E7,E9-E10 (see --list)")
    ap.add_argument("--all", action="store_true", help="run every step in order")
    ap.add_argument("--e15-max-n", type=int, default=None,
                    help="largest cloned registry in E15 (paper: 100000, ~35 min engine build and 3 GB)")
    ap.add_argument("--list", action="store_true", help="list the steps and exit")
    a = ap.parse_args()
    if a.list or not (a.all or a.only):
        print(f"{'step':9} {'minutes':>14}  description")
        for k in ORDER:
            print(f"{k:9} {STEPS[k][3]:>14}  {STEPS[k][0]}")
        return
    out = Path(a.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    if out.resolve() == REFERENCE.resolve():
        print("WARNING: writing into the reference results directory results/final")
    steps = ORDER if a.all else [s.strip() for s in a.only.split(",") if s.strip()]
    unknown = [s for s in steps if s not in STEPS]
    if unknown:
        sys.exit(f"unknown steps {unknown}; see --list")
    if "E1-E3" in steps and "data" not in steps:
        steps = ["data"] + steps
    extra = ["--e15-max-n", str(a.e15_max_n)] if a.e15_max_n else []
    log_path = out / "run_log.json"
    hist = json.load(open(log_path)) if log_path.exists() else []

    def log(msg: str) -> None:
        print(msg, flush=True)

    for s in [x for x in ORDER if x in steps]:
        log(f"[{time.strftime('%H:%M:%S')}] {s}: {STEPS[s][0]}")
        rec = run_step(s, out, extra, log)
        rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        hist.append(rec)
        json.dump(hist, open(log_path, "w"), indent=1)
        log(f"[{time.strftime('%H:%M:%S')}] {s}: {rec['status']} in {rec['seconds']:.0f} s")


if __name__ == "__main__":
    main()
