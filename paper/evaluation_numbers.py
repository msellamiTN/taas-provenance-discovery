"""Every number cited in paper/sections/evaluation.tex, read from results/*.json, plus the statistics the
section reports (paired Wilcoxon signed-rank tests, Wilson score intervals, bootstrap CIs).

No experiment is run here. Output: paper/evaluation_numbers.json (and a printed summary).
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"


def L(name):
    return json.load(open(R / f"{name}.json"))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def boot_diff(a, b, B=5000, seed=0):
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), (B, len(a)))
    d = (a[idx] - b[idx]).mean(axis=1)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def paired(rows, src, sys_a, sys_b, metric):
    by = defaultdict(dict)
    for r in rows:
        if r["source"] == src and r["system"] in (sys_a, sys_b):
            by[r["id"]][r["system"]] = r[metric]
    pairs = [(v[sys_a], v[sys_b]) for v in by.values()
             if sys_a in v and sys_b in v and v[sys_a] == v[sys_a] and v[sys_b] == v[sys_b]]
    a, b = zip(*pairs)
    nz = sum(1 for x, y in pairs if x != y)
    try:
        p = float(stats.wilcoxon(a, b, zero_method="wilcox").pvalue) if nz else 1.0
    except ValueError:
        p = 1.0
    lo, hi = boot_diff(a, b)
    return {"n": len(pairs), "nonzero_pairs": nz, "mean_a": float(np.mean(a)), "mean_b": float(np.mean(b)),
            "mean_diff": float(np.mean(a) - np.mean(b)), "diff_ci95": [lo, hi], "wilcoxon_p": p,
            "a_lower": sum(1 for x, y in pairs if x < y), "a_higher": sum(1 for x, y in pairs if x > y)}


def main() -> None:
    out: dict = {}
    d = json.load(open(ROOT / "data/processed/registry_merged.json"))
    st = d["stats"]
    lt = d["tasks_livemcpbench"]
    out["setup"] = {
        "registry": {k: st[k] for k in ("LiveMCPTool", "MCPToolBench++", "merged")},
        "requests": st["requests"],
        "live_tasks": len(lt), "live_gold_mentions": sum(len(t["gold_tools"]) + len(t["gold_unresolved"]) for t in lt),
        "live_gold_unresolved": sum(len(t["gold_unresolved"]) for t in lt),
        "live_gold_ambiguous": sum(1 for t in lt for g in t["gold_tools"] if "|" in g),
        "live_mean_gold": float(np.mean([len(t["gold_tools"]) for t in lt])),
        "live_categories": sorted({t["category"] for t in lt}),
    }
    silver = json.load(open(ROOT / "data/llm_records/silver_labels.json"))
    out["setup"]["silver"] = {"tools": len(silver), "modifies_state": sum(bool(v.get("modifies_state")) for v in silver.values()),
                              "private_source": sum(bool(v.get("private_source")) for v in silver.values())}
    prompts = json.load(open(ROOT / "data/llm_inputs/analyst_prompts.json"))
    out["setup"]["analyst_prompts"] = dict(Counter(p["source"] for p in prompts))
    cal = json.load(open(ROOT / "data/calibration/index.json"))
    out["setup"]["calibration"] = {"items": len(cal), "classes": sorted({c["class"] for c in cal}),
                                   "sizes": sorted({c["n"] for c in cal})}
    out["calibration"] = L("calibration_table")
    out["e0"] = L("e0_registry")

    e2 = L("e2_eligibility")
    s2 = e2["summary"]
    out["e2"] = {k: {m: v[m]["mean"] for m in ("exposure", "unsafe_share", "safe_retention", "eligible")} | {
        "exposure_ci95": v["exposure"]["ci95"]} for k, v in s2.items()}
    out["e2_coverage"] = {}
    for rf in sorted({r["runnable"] for r in e2["coverage"]}):
        sel = [r for r in e2["coverage"] if r["runnable"] == rf]
        out["e2_coverage"][str(rf)] = {"exposure": float(np.mean([r["exposure"] for r in sel])),
                                       "safe_retention": float(np.mean([r["safe_retention"] for r in sel]))}

    e3 = L("e3_gap_sonnet")
    out["e3_summary"] = {k: {"size": v["size"]["mean"], "tokens": v["tokens"]["mean"], "recall": v["recall"]["mean"],
                             "recall_ci95": v["recall"]["ci95"], "boundary_recall": v["boundary_recall"]["mean"],
                             "precision": v["precision"]["mean"], "abstain": v["abstain_rate"], "valid": v["valid_rate"],
                             "time_s": v["time_s"]["mean"]} for k, v in e3["summary"].items()}
    rows = e3["rows"]
    out["e3_tests"] = {}
    for src in ("LiveMCPBench", "MCPToolBench++"):
        for a, b, m in (("ours", "ours-nogap", "size"), ("ours", "ours-nogap", "recall"),
                        ("ours", "ours-nogap", "tokens"), ("ours", "per-subtask", "recall"),
                        ("ours", "per-subtask", "size"), ("ours", "per-subtask", "tokens"),
                        ("ours", "rag-top5", "recall"), ("ours", "mcp-zero", "recall"),
                        ("ours", "ours-strict", "size"), ("ours", "per-subtask-gap", "recall")):
            out["e3_tests"][f"{src}|{a}|{b}|{m}"] = paired(rows, src, a, b, m)
    bet = [r["beta"] for r in rows if r["system"] == "ours" and r["source"] == "LiveMCPBench" and r["beta"] == r["beta"]]
    out["e3_bridge_ratio_live"] = {"mean": float(np.mean(bet)), "n": len(bet), "share_zero": float(np.mean([b == 0 for b in bet]))}
    gaps = [r for r in rows if r["system"] == "ours" and r["source"] == "LiveMCPBench"]
    out["e3_gap_live"] = {"mean_goals": float(np.mean([r["n_goals"] for r in gaps])),
                          "mean_gap": float(np.mean([r["gap"] for r in gaps])),
                          "share_model_covered": 1 - float(np.sum([r["gap"] for r in gaps]) / np.sum([r["n_goals"] for r in gaps])),
                          "refined": float(np.mean([r["refined"] for r in gaps])),
                          "chi": dict(Counter(r["chi"] for r in gaps if r["chi"]))}
    tune = L("e3_tune")
    out["e3_tune"] = {"selected": tune["selected"], "grid": {k: v["recall"]["mean"] for k, v in tune["grid"].items()}}

    e4 = L("e4_injection")
    out["e4"] = {}
    for name in e4["summary"]:
        sel = [r for r in e4["rows"] if r["system"] == name and r["scope"] == "out"]
        k = sum(r["worst"] for r in sel)
        ks = sum(r["stoch"] for r in sel)
        out["e4"][name] = {"n_out": len(sel), "worst_k": k, "worst": k / len(sel), "worst_wilson": wilson(k, len(sel)),
                           "stoch": ks / len(sel), "stoch_wilson": wilson(ks, len(sel)),
                           "by_attack": {a: sum(r["worst"] for r in sel if r["attack"] == a) /
                                         max(1, sum(1 for r in sel if r["attack"] == a))
                                         for a in ("exfiltrate", "destroy", "execute", "pay", "tamper")},
                           "recall": e4["summary"][name]["recall"]["mean"], "size": e4["summary"][name]["size"]["mean"]}
    p1 = e4["property1"]
    out["e4_property1"] = {k: v | {"flow_rate": v["flow_violations"] / v["sequences"],
                                   "flow_wilson": wilson(v["flow_violations"], v["sequences"])} for k, v in p1.items()}
    out["e4_property1_total"] = {"sequences": sum(v["sequences"] for v in p1.values()),
                                 "effect_violations": sum(v["effect_violations"] for v in p1.values())}

    e5 = L("e5_synthetic")
    out["e5"] = {}
    for name, v in e5["summary"].items():
        sel = [r for r in e5["rows"] if r["system"] == name]
        k = sum(bool(r["valid"]) for r in sel)
        byL = {L_: sum(bool(r["valid"]) for r in sel if r["L"] == L_) / sum(1 for r in sel if r["L"] == L_)
               for L_ in sorted({r["L"] for r in sel})}
        out["e5"][name] = {"n": len(sel), "valid_k": k, "valid": v["valid_rate"], "valid_wilson": wilson(k, len(sel)),
                           "optimal": v["optimal_rate"], "abstain": v["abstain_rate"], "size": v["size"]["mean"],
                           "time_ms": v["time_s"]["mean"] * 1000, "by_L": byL}

    e6 = L("e6_ablations")
    out["e6"] = {"retrieval": e6["retrieval"], "sanitisation": e6["sanitisation"],
                 "path": {k: {"recall": v["recall"]["mean"], "size": v["size"]["mean"], "abstain": v["abstain"],
                              "valid": v["valid"]} for k, v in e6["path"].items()}}
    e7 = L("e7_scalability")
    out["e7"] = {"latency": e7["latency"], "prop3": e7["prop3"], "lemma1": e7["lemma1"],
                 "maintenance": {k: v for k, v in e7["maintenance"].items() if k != "rug_pull"} |
                 {"rug_pull": {k: v for k, v in e7["maintenance"]["rug_pull"].items() if k != "events"}}}
    e8 = L("e8_mcpbench_adapter_fixed")
    out["e8"] = {k: {m: v[m] for m in ("runner_abstain", "recall", "recall_when_run", "size_when_run",
                                        "read_only_runner_abstain", "read_only_recall", "goal_specs_with_unknown_kinds",
                                        "n")} for k, v in e8["summary"].items()}
    v10 = [json.loads(l) for l in open(ROOT / "data/llm_records/analyst_mcpbench_prompt_v1_0_sonnet.jsonl")]
    out["e8_prompt10_unknown_kinds_specs"] = sum(1 for x in v10 if any(
        str(t).split(":")[0].split("[")[0] not in ("text", "document", "table", "record", "media", "credential",
                                                   "identifier", "location", "number", "url", "path", "query", "code",
                                                   "datetime", "boolean", "none")
        for g in x["goals"] for t in list(g.get("in", [])) + [g.get("out", "text")]))
    (ROOT / "paper" / "evaluation_numbers.json").write_text(json.dumps(out, indent=1, default=float))
    T = out["e3_tests"]
    for k in ("LiveMCPBench|ours|ours-nogap|size", "LiveMCPBench|ours|ours-nogap|recall",
              "LiveMCPBench|ours|per-subtask|recall", "LiveMCPBench|ours|per-subtask|tokens",
              "MCPToolBench++|ours|ours-nogap|size", "MCPToolBench++|ours|per-subtask|recall"):
        t = T[k]
        print(f"{k:42s} n={t['n']} {t['mean_a']:.3f} vs {t['mean_b']:.3f} diff={t['mean_diff']:+.3f} "
              f"CI[{t['diff_ci95'][0]:+.3f},{t['diff_ci95'][1]:+.3f}] p={t['wilcoxon_p']:.2g}")
    for k, v in out["e4"].items():
        print(f"E4 {k:28s} {v['worst_k']}/{v['n_out']} = {v['worst']:.3f} Wilson {v['worst_wilson'][0]:.3f}-{v['worst_wilson'][1]:.3f}")
    for k, v in out["e5"].items():
        print(f"E5 {k:16s} {v['valid_k']}/{v['n']} Wilson lo {v['valid_wilson'][0]:.3f} byL {v['by_L']}")
    print("gap", out["e3_gap_live"], "beta", out["e3_bridge_ratio_live"])
    print("setup", {k: out["setup"][k] for k in ("live_tasks", "live_gold_mentions", "live_gold_unresolved",
                                                 "live_gold_ambiguous", "live_mean_gold", "silver", "analyst_prompts")})
    print("coverage", out["e2_coverage"])
    print("prompt 1.0 specs with unknown kinds:", out["e8_prompt10_unknown_kinds_specs"])


if __name__ == "__main__":
    main()
