"""E9 multi-tool set retrieval and E10 set validity on the LiveMCPBench test tasks with a resolvable gold
tool (94).

E9 (open policy, as in Section 8.4): group recall, complete-set share (COLT's COMP), set precision, size and
tokens for k in {5, 10, 20}; decomposition in {none, clause splitter, LLM analyst} for the methods that take
subqueries; size-matched comparison (ranked baselines truncated to PaMCP's |K| per task).
E10 (least-privilege policy of each task): joint feasibility and per-check pass rates from the independent
set evaluator; baselines both as published (no policy) and restricted to the eligible pool; PaMCP candidate
budget K in {10, 20, 40}.
"""
from __future__ import annotations

import math
from collections import defaultdict

import fe
import methods as M
import set_evaluator as SE

KS = (5, 10, 20)


def interleave(rankings: list[list[str]], k: int) -> list[str]:
    out = []
    for i in range(max((len(r) for r in rankings), default=0)):
        for r in rankings:
            if i < len(r) and r[i] not in out:
                out.append(r[i])
            if len(out) >= k:
                return out
    return out


def main() -> None:
    tasks = [t for t in fe.tasks_live() if t["gold"]]
    worlds = {k: M.World(K=k) for k in (5, 10, 20, 40)}
    w = worlds[5]
    w_nc = M.World(depth=0)
    mz, ts = M.MCPZero(w), M.ToolScope(w)
    colt = M.COLT(w, {t["query"] for t in fe.tasks_dev() + fe.tasks_e8_sample()})
    cm = M.CMTF(w)
    pol_open = M.open_policy()
    rows9, rows10 = [], []
    for t in tasks:
        spec, rec = fe.spec_for(t)
        if spec is None:
            continue
        G = t["gold"]
        decomp = {"none": [t["query"]], "clause": M.clause_split(t["query"]), "analyst": M.subqueries(spec)}
        sets: dict[str, list[str]] = {}
        meta: dict[str, dict] = {}
        # PaMCP (open policy) with retrieval budget K = k, and without backward closure
        for k in KS:
            r = (w if k == 5 else worlds[k]).pamcp(1, 1, 1, spec, rec, pol_open)
            sets[f"pamcp@{k}"] = r["K"]
            meta[f"pamcp@{k}"] = {"abstain": r["abstain"], "certified": r["valid"], "chi": r["chi"]}
        r = w_nc.pamcp(1, 1, 1, spec, rec, pol_open)
        sets["pamcp_noclosure"] = r["K"]
        meta["pamcp_noclosure"] = {"abstain": r["abstain"], "certified": r["valid"], "chi": r["chi"]}
        sets["mcp_zero"] = mz.select(t["id"], w.pool, 1)
        sets["cmtf_path"] = cm.plan(spec, w.pool)["path"]
        for dname, sq in decomp.items():
            sets[f"per_subtask[{dname}]"] = interleave([w.rank(q, w.pool, ("lex", "den"))[:1] for q in sq], 99)
        for k in KS:
            sets[f"rag_mcp@{k}"] = w.rank(t["query"], w.pool, ("den",))[:k]
            sets[f"colt@{k}"] = colt.ranked(t["query"], w.pool)[:k]
            sets[f"mcp_zero_ranked@{k}"] = mz.ranked(t["id"], w.pool)[:k]
            for dname, sq in decomp.items():
                sets[f"toolscope[{dname}]@{k}"] = sorted(ts.expand(ts.select(t["query"], sq if dname != "none" else [],
                                                                             w.pool, k)))
                sets[f"per_subtask[{dname}]@{k}"] = interleave([w.rank(q, w.pool, ("lex", "den")) for q in sq], k)
        for name, K in sets.items():
            rows9.append({"id": t["id"], "method": name, "size": len(K), "tokens": w.tokens(K),
                          "recall": fe.group_recall(K, G), "complete": fe.complete(K, G),
                          "precision": fe.set_precision(K, G), "n_gold_groups": len(G),
                          **meta.get(name, {"abstain": False, "certified": None, "chi": ""}), "toolkit": K})
        # size-matched: ranked baselines truncated to PaMCP@5's size
        n = len(sets["pamcp@5"])
        if n:
            ranked = {"rag_mcp": w.rank(t["query"], w.pool, ("den",)), "colt": colt.ranked(t["query"], w.pool),
                      "mcp_zero_ranked": mz.ranked(t["id"], w.pool),
                      "per_subtask[analyst]": interleave([w.rank(q, w.pool, ("lex", "den"))
                                                          for q in decomp["analyst"]], 99)}
            for name, r in ranked.items():
                K = r[:n]
                rows9.append({"id": t["id"], "method": f"{name}@size-matched", "size": len(K),
                              "tokens": w.tokens(K), "recall": fe.group_recall(K, G), "complete": fe.complete(K, G),
                              "precision": fe.set_precision(K, G)})
            rows9.append({"id": t["id"], "method": "pamcp@size-matched", "size": n, "tokens": w.tokens(sets["pamcp@5"]),
                          "recall": fe.group_recall(sets["pamcp@5"], G), "complete": fe.complete(sets["pamcp@5"], G),
                          "precision": fe.set_precision(sets["pamcp@5"], G)})
        # ------------------------------------------------------------- E10 under least privilege
        pol, need = M.least_privilege(rec)
        elig = set(w.eligible(1, pol))
        e10 = {}
        m10 = {}
        for k in (10, 20, 40):
            r = worlds[k].pamcp(1, 1, 1, spec, rec, pol)
            e10[f"pamcp(K={k})"] = (r["K"], r["abstain"])
            m10[f"pamcp(K={k})"] = {"certified": r["valid"], "chi": r["chi"]}
        r = w.pamcp(1, 1, 0, spec, rec, pol)
        e10["pamcp_nocert"] = (r["K"], False)
        pool_e = sorted(elig)
        base_sets = {"rag_mcp@5": (w.rank(t["query"], w.pool, ("den",))[:5],
                                   w.rank(t["query"], pool_e, ("den",))[:5]),
                     "colt@5": (colt.ranked(t["query"], w.pool)[:5], colt.ranked(t["query"], pool_e)[:5]),
                     "mcp_zero": (mz.select(t["id"], w.pool, 1), mz.select(t["id"], pool_e, 1)),
                     "toolscope[analyst]@5": (sorted(ts.expand(ts.select(t["query"], decomp["analyst"], w.pool, 5))),
                                              sorted(ts.expand(ts.select(t["query"], decomp["analyst"], pool_e, 5)))),
                     "cmtf_path": (cm.plan(spec, w.pool)["path"], cm.plan(spec, pool_e)["path"]),
                     "per_subtask[analyst]": (sets["per_subtask[analyst]"],
                                              interleave([w.rank(q, pool_e, ("lex", "den"))[:1]
                                                          for q in decomp["analyst"]], 99))}
        for name, (unf, fil) in base_sets.items():
            e10[f"{name}|unfiltered"] = (unf, False)
            e10[f"{name}|eligible-only"] = (fil, False)
        for name, (K, ab) in e10.items():
            ev = SE.evaluate(K, rec, need, verified=elig)
            rows10.append({"id": t["id"], "method": name, "abstain": ab, "size": len(K),
                           "recall": fe.group_recall(K, G), **ev,
                           **m10.get(name, {"certified": None, "chi": ""}), "toolkit": K})
    methods9 = sorted({r["method"] for r in rows9})
    s9 = fe.summarise(rows9, ["method"], ["size", "tokens", "recall", "complete", "precision"])
    # paired tests (recall) PaMCP@5 vs comparators at k=5 and size-matched
    by = defaultdict(dict)
    for r in rows9:
        by[r["method"]][r["id"]] = r
    tests = {}
    for comp in ["rag_mcp@5", "colt@5", "mcp_zero", "mcp_zero_ranked@5", "toolscope[analyst]@5", "cmtf_path",
                 "per_subtask[analyst]", "pamcp_noclosure"]:
        ids = sorted(set(by["pamcp@5"]) & set(by[comp]))
        tests[f"pamcp@5 vs {comp}"] = fe.paired([by["pamcp@5"][i]["recall"] for i in ids],
                                                 [by[comp][i]["recall"] for i in ids], margin=0.05)
    for comp in ["rag_mcp", "colt", "mcp_zero_ranked", "per_subtask[analyst]"]:
        a, b = by["pamcp@size-matched"], by[f"{comp}@size-matched"]
        ids = sorted(set(a) & set(b))
        tests[f"size-matched pamcp vs {comp}"] = fe.paired([a[i]["recall"] for i in ids], [b[i]["recall"] for i in ids])
    s10 = {}
    for m in sorted({r["method"] for r in rows10}):
        sel = [r for r in rows10 if r["method"] == m]
        n = len(sel)
        s10[m] = {"n": n, "abstain": sum(r["abstain"] for r in sel) / n,
                  "certified": (sum(1 for r in sel if r["certified"]) / n) if sel[0]["certified"] is not None else None,
                  "joint_among_non_abstained": (sum(r["joint"] for r in sel if not r["abstain"]) /
                                                max(1, sum(1 for r in sel if not r["abstain"]))),
                  "joint_feasible": sum(r["joint"] for r in sel) / n,
                  "joint_ci": fe.wilson(sum(r["joint"] for r in sel), n),
                  "pass": {c: sum(1 for r in sel if r[c]) / n for c in ("S", "C", "E", "L", "V", "M")},
                  "interface_mismatch_mean": fe.nanmean(r["interface_mismatch"] for r in sel),
                  "forbidden_tools_mean": fe.nanmean(r["forbidden_tools"] for r in sel),
                  "flow_violations": sum(r["flow_violation"] for r in sel),
                  "recall": fe.nanmean(r["recall"] for r in sel), "size": fe.nanmean(r["size"] for r in sel)}
    # paired joint feasibility tests: PaMCP(K=40, the default composer budget is K=5 retrieval per goal) vs others
    by10 = defaultdict(dict)
    for r in rows10:
        by10[r["method"]][r["id"]] = r
    t10 = {}
    for comp in [m for m in s10 if m != "pamcp(K=10)"]:
        ids = sorted(set(by10["pamcp(K=10)"]) & set(by10[comp]))
        t10[f"pamcp(K=10) vs {comp}"] = fe.paired([float(by10["pamcp(K=10)"][i]["joint"]) for i in ids],
                                                   [float(by10[comp][i]["joint"]) for i in ids])
    abst9 = {m: {"abstain_rate": sum(1 for r in rows9 if r["method"] == m and r.get("abstain")) /
                                 max(1, sum(1 for r in rows9 if r["method"] == m)),
                 "certified_rate": (sum(1 for r in rows9 if r["method"] == m and r.get("certified")) /
                                    max(1, sum(1 for r in rows9 if r["method"] == m)))
                 if any(r.get("certified") is not None for r in rows9 if r["method"] == m) else None,
                 "chi": dict(__import__("collections").Counter(r.get("chi") for r in rows9
                                                               if r["method"] == m and r.get("chi")))}
             for m in methods9}
    fe.save("E9_sets", {"summary": s9, "abstention_and_certification": abst9, "tests": tests, "methods": methods9,
                        "n_tasks": len(tasks)},
            "MEASURED against LiveMCPBench gold chains (recorded analyst, MCP-Zero and LLM-assisted baselines)",
            config={"policy": "open", "k": list(KS), "decomposition": ["none", "clause", "analyst"],
                    "size_matched_to": "pamcp@5", "noninferiority_margin": 0.05},
            raw=fe.save_raw("E9_sets", rows9))
    fe.save("E10_validity", {"summary": s10, "tests": t10},
            "LABELLED: independent set evaluator over labels B; V from simulated verifier evidence (labels A)",
            config={"policy": "least privilege per task", "pamcp_K": [10, 20, 40], "baselines": "unfiltered and "
                    "eligible-only", "evaluator": "experiments/final/set_evaluator.py"},
            raw=fe.save_raw("E10_validity", rows10))
    for m in ("pamcp@5", "pamcp@10", "pamcp@20", "rag_mcp@5", "colt@5", "mcp_zero", "toolscope[analyst]@5", "cmtf_path",
              "per_subtask[analyst]", "pamcp_noclosure"):
        v = s9[m]
        print(f"E9 {m:24s} |K| {v['size']['mean']:.2f} tok {v['tokens']['mean']:.0f} rec {v['recall']['mean']:.3f} "
              f"comp {v['complete']['mean']:.3f} prec {v['precision']['mean']:.3f}")
    for m, v in s10.items():
        print(f"E10 {m:40s} joint {v['joint_feasible']:.3f} abst {v['abstain']:.2f} pass {v['pass']}")


if __name__ == "__main__":
    main()
