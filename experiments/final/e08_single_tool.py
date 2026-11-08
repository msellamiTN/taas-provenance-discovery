"""E8 single-tool retrieval on MCPToolBench++.

Registries: B1 = the 87 MCPToolBench++ tools, B1m = the merged 569-tool registry, and B1 plus d random
LiveMCPTool distractors (d in {50, 150, 300, 482}; 5 seeds). Request interpreter: raw text or the analyst's
goal contract. Evaluation sets: the 300-query sample (every method, including those that need recorded LLM
outputs) and all 1,509 requests (methods without LLM inputs). CIs: percentile bootstrap with target tools as
clusters (E22 compares resampling units).
"""
from __future__ import annotations

import random
from collections import defaultdict

import numpy as np

import fe
import methods as M

KS = (1, 5)


def target(task) -> str:
    return sorted(task["gold"][0])[0]


def run_set(tasks, pool, rankers: dict, label: str) -> tuple[dict, list[dict]]:
    rows = []
    for t in tasks:
        for name, f in rankers.items():
            r = f(t, pool)
            if r is None:
                continue
            row = {"id": t["id"], "category": t["category"], "target": target(t), "method": name,
                   "hit1": fe.hit_at(r, t["gold"], 1), "hit5": fe.hit_at(r, t["gold"], 5),
                   "mrr10": fe.mrr_at(r, t["gold"], 10)}
            rows.append(row)
    summ = {}
    for name in rankers:
        sel = [r for r in rows if r["method"] == name]
        if not sel:
            continue
        cl = [r["target"] for r in sel]
        m = {x: {"mean": fe.nanmean(r[x] for r in sel), "ci_target": fe.boot_ci([r[x] for r in sel], clusters=cl),
                 "ci_request": fe.boot_ci([r[x] for r in sel])} for x in ("hit1", "hit5", "mrr10")}
        per_t = defaultdict(list)
        for r in sel:
            per_t[r["target"]].append(r["hit1"])
        m["tool_macro_hit1"] = float(np.mean([np.mean(v) for v in per_t.values()]))
        m["n"] = len(sel)
        m["n_targets"] = len(per_t)
        summ[name] = m
    return summ, rows


def main() -> None:
    w = M.World()
    mz, ts = M.MCPZero(w), M.ToolScope(w)
    sample, full = fe.tasks_e8_sample(), fe.tasks_pp_all()
    dev = fe.tasks_dev()
    colt_s = M.COLT(w, {t["query"] for t in sample + dev})
    colt_f = M.COLT(w, {t["query"] for t in full})          # generated scenes only
    cm = M.CMTF(w)
    pp_ids = sorted({t.id for t in fe.raw() if t.source == "MCPToolBench++"}
                    | {g for t in full for grp in t["gold"] for g in grp})
    B1 = [t for t in pp_ids if t in w.ret.pos]
    others = [t for t in w.pool if t not in set(B1)]

    def contract_rank(t, pool):
        spec, rec = fe.spec_for(t)
        if spec is None:
            return None
        goals = [g for g in spec.goals if not g.optional] or spec.goals
        rk = []
        for g in goals:
            s = w.ret.scores(g.rendering(), g.out, pool, set(), components=("lex", "den", "str"))
            rk.append([x for x, _ in sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))])
        out = []
        for i in range(max(len(x) for x in rk)):
            for x in rk:
                if i < len(x) and x[i] not in out:
                    out.append(x[i])
        return out

    def ts_rank(t, pool):
        mp = ts.merged_pool(pool)
        reps = w.rank(t["query"], mp, ("den",))
        out = []
        for r in reps:                         # a merged tool counts as each of its members (ToolScope's remapping)
            for m in ts.clusters.get(r, [r]):
                if m in set(pool) and m not in out:
                    out.append(m)
        return out

    def cmtf_rank(t, pool):
        spec, rec = fe.spec_for(t)
        if spec is None:
            return None
        p = cm.plan(spec, pool)
        rest = contract_rank(t, pool) or []
        return p["frontier"] + [x for x in rest if x not in p["frontier"]]

    def mz_rank(t, pool):
        return mz.ranked(t["id"], pool) if mz.requests(t["id"]) is not None else None

    base = {"bm25": lambda t, p: w.rank(t["query"], p, ("lex",)),
            "dense_lsa": lambda t, p: w.rank(t["query"], p, ("den",)),
            "rrf": lambda t, p: w.rank(t["query"], p, ("lex", "den"))}
    rankers_s = dict(base) | {"pamcp_contract": contract_rank, "mcp_zero": mz_rank,
                              "colt_adapted": lambda t, p: colt_s.ranked(t["query"], p),
                              "toolscope_adapted": ts_rank, "cmtf_adapted": cmtf_rank}
    res = {"registries": {"B1": len(B1), "B1m": len(w.pool)}}
    allrows = {}
    for reg_name, pool in (("B1", B1), ("B1m", w.pool)):
        s, rows = run_set(sample, pool, rankers_s, reg_name)
        res[f"sample|{reg_name}"] = s
        allrows[f"sample|{reg_name}"] = rows
        print(reg_name, {k: round(v["hit1"]["mean"], 3) for k, v in s.items()})
    rankers_f = dict(base) | {"colt_adapted": lambda t, p: colt_f.ranked(t["query"], p)}
    for reg_name, pool in (("B1", B1), ("B1m", w.pool)):
        s, rows = run_set(full, pool, rankers_f, reg_name)
        res[f"full|{reg_name}"] = s
        allrows[f"full|{reg_name}"] = rows
    # distractor curve
    curve = {}
    for d in (0, 50, 150, 300, len(others)):
        accs = defaultdict(list)
        for sd in range(5 if 0 < d < len(others) else 1):
            rng = random.Random(sd)
            pool = B1 + (rng.sample(others, d) if d < len(others) else others)
            s, _ = run_set(sample, pool, {k: v for k, v in rankers_s.items() if k != "cmtf_adapted"}, f"B1+{d}")
            for k, v in s.items():
                accs[k].append(v["hit1"]["mean"])
        curve[str(d)] = {k: float(np.mean(v)) for k, v in accs.items()}
    res["distractor_curve_hit1"] = curve
    # paired tests on the sample (B1m), against pamcp_contract and rrf
    rows = allrows["sample|B1m"]
    by = defaultdict(dict)
    for r in rows:
        by[r["method"]][r["id"]] = r
    tests = {}
    for ref in ("pamcp_contract",):
        for m in rankers_s:
            if m == ref:
                continue
            ids = sorted(set(by[ref]) & set(by[m]))
            tests[f"{ref} vs {m}|hit1"] = fe.paired([by[ref][i]["hit1"] for i in ids], [by[m][i]["hit1"] for i in ids])
    res["tests_sample_B1m"] = tests
    fe.save("E8_single_tool", {"results": res, "rows": allrows},
            "MEASURED (gold labels of MCPToolBench++); LLM inputs recorded (analyst contracts, MCP-Zero requests)",
            inputs=["data/llm_inputs/final/e8_sample.json"])
    print("curve", curve)


if __name__ == "__main__":
    main()
