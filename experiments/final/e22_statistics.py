"""E22 statistical validity and reproducibility, and the preregistered confirmatory family F1-F7
(docs/FINAL_EVALUATION_PLAN.md) with Holm correction.

* resampling unit: CI width of E8 Hit@1 with requests vs target tools as the bootstrap unit;
* split type: stability of the method ranking (E8 Hit@1, B1m sample) across 200 random half splits that are
  stratified by category or tool-disjoint (targets partitioned); Kendall's tau between halves and the share of
  splits with the same best method.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from itertools import combinations

import numpy as np

import fe


def load(name):
    return json.load(open(fe.RES / f"{name}.json"))


def kendall(a: list[str], b: list[str]) -> float:
    pa, pb = {m: i for i, m in enumerate(a)}, {m: i for i, m in enumerate(b)}
    c = d = 0
    for x, y in combinations(a, 2):
        s = (pa[x] - pa[y]) * (pb[x] - pb[y])
        c += s > 0
        d += s < 0
    return (c - d) / max(1, c + d)


def split_stability(rows, n_splits: int = 200) -> dict:
    by = defaultdict(dict)
    for r in rows:
        by[r["method"]][r["id"]] = r
    methods = sorted(by)
    ids = sorted(set.intersection(*[set(v) for v in by.values()]))
    cat = {i: by[methods[0]][i]["category"] for i in ids}
    tgt = {i: by[methods[0]][i]["target"] for i in ids}
    out = {}
    for mode in ("stratified", "tool_disjoint"):
        taus, same = [], 0
        rng = random.Random(0)
        for _ in range(n_splits):
            if mode == "stratified":
                h1 = set()
                for c in sorted(set(cat.values())):   # sorted: the split must not depend on PYTHONHASHSEED
                    xs = [i for i in ids if cat[i] == c]
                    rng.shuffle(xs)
                    h1 |= set(xs[: len(xs) // 2])
            else:
                ts = sorted(set(tgt.values()))
                rng.shuffle(ts)
                tset = set(ts[: len(ts) // 2])
                h1 = {i for i in ids if tgt[i] in tset}
            h2 = set(ids) - h1
            r1 = sorted(methods, key=lambda m: -np.mean([by[m][i]["hit1"] for i in h1]))
            r2 = sorted(methods, key=lambda m: -np.mean([by[m][i]["hit1"] for i in h2]))
            taus.append(kendall(r1, r2))
            same += r1[0] == r2[0]
        out[mode] = {"kendall_tau_mean": float(np.mean(taus)), "kendall_tau_p5": float(np.percentile(taus, 5)),
                     "same_best_share": same / n_splits, "n_splits": n_splits}
    return out


def f4_rows() -> dict:
    """Per-request paired Exp@5 for F4 (E4 saved aggregates only): recomputed at coverage 1."""
    import e04_e07_exposure as X
    import methods as M
    from taas.realreg import build_contracts
    A, B = fe.labels_A(), fe.labels_B()
    raw = fe.raw()
    cs = build_contracts(raw, None)
    rk = X.Rankers(cs, None, None, None)
    el = X.eligibility(raw, cs, X.verifier_decisions(raw, A, rho=1.0, seed=0))
    a, b = [], []
    for r in X.requests():
        if not all(all(not B[t].unsafe_read_only for t in g if t in B) for g in r["gold"]):
            continue
        for enc, lst in (("verified_evidence", a), ("lexical_positive", b)):
            top = rk.rank("pamcp_rrf", r, el[enc], 5)
            lst.append(float(any(B[t].unsafe_read_only for t in top)))
    return fe.paired(a, b)


def main() -> None:
    e8 = load("E8_single_tool")
    res = {"resampling_unit": {}, "split_stability": None, "family": {}}
    for m, v in e8["results"]["sample|B1m"].items():
        h = v["hit1"]
        res["resampling_unit"][m] = {"mean": h["mean"], "ci_request": h["ci_request"], "ci_target": h["ci_target"],
                                     "width_request": h["ci_request"][1] - h["ci_request"][0],
                                     "width_target": h["ci_target"][1] - h["ci_target"][0]}
    res["split_stability"] = split_stability(e8["rows"]["sample|B1m"])
    # ---------------- confirmatory family
    e9, e10, e18 = load("E9_sets"), load("E10_validity"), load("E18_factorial")
    fam = {}
    t = e9["tests"]["pamcp@5 vs per_subtask[analyst]"]
    fam["F1"] = {"test": "E9 recall non-inferiority PaMCP vs per-subtask (margin 0.05)", "p": t["p_noninferior"],
                 "diff": t["diff"], "ci": t["ci"], "n": t["n"]}
    t = e9["tests"]["size-matched pamcp vs rag_mcp"]
    fam["F2"] = {"test": "E9 size-matched recall PaMCP vs RAG-MCP", "p": t["p"], "diff": t["diff"], "ci": t["ci"],
                 "n": t["n"]}
    t = e10["tests"]["pamcp(K=10) vs per_subtask[analyst]|eligible-only"]
    fam["F3"] = {"test": "E10 joint feasibility PaMCP(K=10) vs per-subtask (eligible)", "p": t["p"], "diff": t["diff"],
                 "ci": t["ci"], "n": t["n"]}
    t = f4_rows()
    fam["F4"] = {"test": "E4 Exp@5 verified vs lexical-positive (coverage 1)", "p": t["p"], "diff": t["diff"],
                 "ci": t["ci"], "n": t["n"]}
    rows = [r for r in fe.load_raw("E18_factorial") if r["policy"] == "least_privilege"]
    by = defaultdict(dict)
    for r in rows:
        by[r["method"]][r["id"]] = r
    a, b = [], []
    for i in sorted(set(by["Full_PaMCP"]) & set(by["per_subtask|unfiltered"])):
        ra, rb = by["Full_PaMCP"][i], by["per_subtask|unfiltered"][i]
        for k in ra:
            if k.startswith("reach_") and k != "reach_any":
                a.append(ra[k])
                b.append(rb[k])
    t = fe.paired(a, b)
    fam["F5"] = {"test": "E14 reachable out-of-scope attacks PaMCP vs per-subtask (task x attack)", "p": t["p"],
                 "diff": t["diff"], "ci": t["ci"], "n": t["n"]}
    ids = sorted(set(by["Full_PaMCP"]) & set(by["PaMCP_NoGap"]))
    t = fe.paired([by["Full_PaMCP"][i]["tokens"] for i in ids], [by["PaMCP_NoGap"][i]["tokens"] for i in ids])
    fam["F6"] = {"test": "E18 tokens Full vs NoGap", "p": t["p"], "diff": t["diff"], "ci": t["ci"], "n": t["n"]}
    t = e8["results"]["tests_sample_B1m"]["pamcp_contract vs rrf|hit1"]
    fam["F7"] = {"test": "E8 Hit@1 goal-contract vs raw-text RRF (B1m sample)", "p": t["p"], "diff": t["diff"],
                 "ci": t["ci"], "n": t["n"]}
    h = fe.holm({k: v["p"] for k, v in fam.items()})
    for k in fam:
        fam[k]["p_holm"] = h[k]
        fam[k]["significant_0.05"] = h[k] < 0.05
    res["family"] = fam
    fe.save("E22_statistics", res, "MEASURED (statistics over the other result files)")
    for k, v in fam.items():
        print(k, v["test"], "diff", round(v["diff"], 4), "p", round(v["p"], 5), "holm", round(v["p_holm"], 5))
    print(res["split_stability"])


if __name__ == "__main__":
    main()
