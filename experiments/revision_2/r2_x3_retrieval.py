"""Revision 2, X3: retrieval and typing diagnosis, and equal-budget tuning of every method.

    python experiments/revision_2/r2_x3_retrieval.py dev     # selection on the 60 development prompts only
    python experiments/revision_2/r2_x3_retrieval.py test    # after the preregistration amendment: the 300-query
                                                             # sample with the configurations selected on dev

PaMCP variants rank from the analyst's goal contract (one ranking per non-optional goal, interleaved), with the
types reachable from the prompt (R0, as in the engine; the paper's E8 used an empty set):
  A lex | B den | C lex+den | D str (den tie-break) | E lex+den+str (Eq. (5)) | F relevance-first, then type-compatible
  first within the top 10 | F2 relevance restricted to type-compatible tools (the engine's candidate filter) |
  G70, G85 structural score only for tools typed with confidence >= 0.70 / 0.85 | W50, W25 structural ranking
  weighted 0.5 / 0.25 in the fusion | I oracle goal types (goal output := the gold tool's J_B output type) |
  J oracle tool types (tool heads := J_B output types) | IJ both oracles.
Baselines (raw request text) with grids of comparable size: BM25 k1 x b, RRF k0, MCP-Zero server budget, COLT
lambda x mu, ToolScope retrieval components, CMTF width x depth. Dense retrieval has no parameter (shared encoder).
Metrics: Hit@1/3/5, MRR@10, nDCG@10; pools B1 (81 MCPToolBench++ tools) and B1m (569 tools); for PaMCP variants
also strata by the typing confidence of the gold tool. Selection rule (fixed before running): highest dev Hit@1 on
B1m, ties broken by MRR@10, then by the smaller configuration index.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402
import methods as M  # noqa: E402
from taas.retrieval import BM25, structural_score  # noqa: E402
from taas.types import parse_type, subtype  # noqa: E402

SPLIT = sys.argv[1] if len(sys.argv) > 1 else "dev"
SEL_PATH = fe.RES / "R2_X3_dev.json"


def ndcg_at(ranked, gold, k=10):
    rel_groups = [set(g) for g in gold]
    seen, dcg = set(), 0.0
    for i, t in enumerate(ranked[:k]):
        for j, g in enumerate(rel_groups):
            if j not in seen and t in g:
                seen.add(j)
                dcg += 1.0 / math.log2(i + 2)
                break
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(rel_groups))))
    return dcg / ideal if ideal else float("nan")


def metrics(ranked, gold):
    return {"hit1": fe.hit_at(ranked, gold, 1), "hit3": fe.hit_at(ranked, gold, 3), "hit5": fe.hit_at(ranked, gold, 5),
            "mrr10": fe.mrr_at(ranked, gold, 10), "ndcg10": ndcg_at(ranked, gold, 10)}


class Ranker:
    def __init__(self, w: M.World):
        self.w = w
        self.ret = w.ret
        self.comp = w.ref.composer
        self.Bd = fe.labels_B_raw()
        self.Bhead = {t: parse_type(v["out"]) for t, v in self.Bd.items() if v.get("out")}
        self._bm25 = {}

    # ------------------------------------------------------------------ PaMCP variants
    def goal_lists(self, t, pool, variant):
        spec, rec = fe.spec_for(t)
        if spec is None:
            return None
        goals = [g for g in spec.goals if not g.optional] or spec.goals
        X = [parse_type(x) for x in spec.prompt_inputs]
        R0 = self.comp._reach([], X, self.comp.model_edges(spec.goals)).types
        gold_type = None
        if variant in ("I", "IJ"):
            for grp in t["gold"]:
                for x in grp:
                    if x in self.Bhead:
                        gold_type = self.Bhead[x]
                        break
                if gold_type is not None:
                    break
        lists = []
        for g in goals:
            gout = gold_type if gold_type is not None else g.out
            lists.append(self.rank_goal(g.rendering(), gout, pool, R0, variant))
        out = []
        for i in range(max(len(x) for x in lists)):
            for x in lists:
                if i < len(x) and x[i] not in out:
                    out.append(x[i])
        return out

    def rank_goal(self, query, gout, pool, R0, variant):
        ret = self.ret
        elig = [x for x in pool if x in ret.pos]
        idx = [ret.pos[x] for x in elig]
        lex = {ret.ids[i]: v for i, v in ret.bm25.scores(query, idx).items()}
        q = ret.encoder.encode([query])[0]
        den = {x: float(v) for x, v in zip(elig, ret.vecs[idx] @ q)}
        kmin = {"G70": 0.70, "G85": 0.85}.get(variant, ret.kappa_min)
        oracle_tools = variant in ("J", "IJ")

        def st(x):
            c = ret.contracts[x]
            if oracle_tools:
                h = self.Bhead.get(x)
                return 0.0 if h is None else structural_score(h, 1.0, c.tail, gout, R0, 0.0)
            return structural_score(c.head, c.out.confidence, c.tail, gout, R0, kmin)
        comps = {"A": ("lex",), "B": ("den",), "C": ("lex", "den"), "D": ("str",), "F": ("lex", "den"),
                 "F2": ("lex", "den")}.get(variant, ("lex", "den", "str"))
        weights = {"lex": 1.0, "den": 1.0, "str": {"W50": 0.5, "W25": 0.25}.get(variant, 1.0)}
        rankings = {}
        if "lex" in comps:
            rankings["lex"] = lex
        if "den" in comps:
            rankings["den"] = den
        if "str" in comps:
            rankings["str"] = {x: st(x) for x in elig}
        fused = {x: 0.0 for x in elig}
        for name, r in rankings.items():
            order = sorted(r.items(), key=lambda kv: (-kv[1], kv[0]))
            for rank, (x, v) in enumerate(order, start=1):
                if v > 0 or len(rankings) == 1:
                    fused[x] += weights[name] / (ret.k0 + rank)
        if variant == "D":     # structural only: ties broken by dense similarity
            order = sorted(elig, key=lambda x: (-rankings["str"][x], -den[x], x))
        else:
            order = [x for x, _ in sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))]
        compat = lambda x: subtype(ret.contracts[x].head, gout) and ret.contracts[x].out.confidence >= ret.kappa_min
        if variant == "F":
            top = order[:10]
            order = sorted(top, key=lambda x: not compat(x)) + order[10:]
        if variant == "F2":
            order = [x for x in order if compat(x)]
        return order

    # ------------------------------------------------------------------ baselines on raw text
    def bm25(self, query, pool, k1, b):
        key = (k1, b)
        if key not in self._bm25:
            self._bm25[key] = BM25([self.ret.contracts[x].rendering() for x in self.ret.ids], k1=k1, b=b)
        idx = [self.ret.pos[x] for x in pool if x in self.ret.pos]
        s = self._bm25[key].scores(query, idx)
        return [self.ret.ids[i] for i, _ in sorted(s.items(), key=lambda kv: (-kv[1], self.ret.ids[kv[0]]))]

    def rrf(self, query, pool, k0):
        old = self.ret.k0
        self.ret.k0 = k0
        try:
            return self.w.rank(query, pool, ("lex", "den"))
        finally:
            self.ret.k0 = old


def configs(R: Ranker, w: M.World, colt_cache: dict, exclude: set[str]):
    """name -> (method, config label, function(task, pool) -> ranked list or None)."""
    out = {}
    for v in ("A", "B", "C", "D", "E", "F", "F2", "G70", "G85", "W50", "W25", "I", "J", "IJ"):
        out[f"pamcp|{v}"] = ("pamcp", v, lambda t, p, v=v: R.goal_lists(t, p, v))
    for k1, b in itertools.product((0.9, 1.2, 1.5, 2.0), (0.5, 0.75, 0.9)):
        out[f"bm25|k1={k1},b={b}"] = ("bm25", f"k1={k1},b={b}", lambda t, p, k1=k1, b=b: R.bm25(t["query"], p, k1, b))
    out["dense|-"] = ("dense", "-", lambda t, p: w.rank(t["query"], p, ("den",)))
    for k0 in (10, 30, 60, 100):
        out[f"rrf|k0={k0}"] = ("rrf", f"k0={k0}", lambda t, p, k0=k0: R.rrf(t["query"], p, k0))
    for sk in (1, 2, 3, 5):
        mz = M.MCPZero(w, servers_k=sk)
        out[f"mcp_zero|servers_k={sk}"] = ("mcp_zero", f"servers_k={sk}",
                                           lambda t, p, mz=mz: mz.ranked(t["id"], p) if mz.requests(t["id"]) else None)
    for lam, mu in itertools.product((0.0, 0.25, 0.5, 1.0), (0.0, 0.25, 0.5, 1.0)):
        key = (lam, mu)
        if key not in colt_cache:
            colt_cache[key] = M.COLT(w, exclude, lam=lam, mu=mu)
        out[f"colt|lam={lam},mu={mu}"] = ("colt", f"lam={lam},mu={mu}",
                                         lambda t, p, c=colt_cache[key]: c.ranked(t["query"], p))
    ts = M.ToolScope(w)
    for comps in (("den",), ("lex", "den"), ("lex",)):
        def ts_rank(t, p, comps=comps):
            mp = ts.merged_pool(p)
            reps = w.rank(t["query"], mp, comps)
            res, ps = [], set(p)
            for r in reps:
                for m in ts.clusters.get(r, [r]):
                    if m in ps and m not in res:
                        res.append(m)
            return res
        out[f"toolscope|{'+'.join(comps)}"] = ("toolscope", "+".join(comps), ts_rank)
    for N, depth in itertools.product((20, 40), (4, 6)):
        cm = M.CMTF(w, N=N, depth=depth)

        def cm_rank(t, p, cm=cm):
            spec, rec = fe.spec_for(t)
            if spec is None:
                return None
            plan = cm.plan(spec, p)
            rest = R.goal_lists(t, p, "E") or []
            return plan["frontier"] + [x for x in rest if x not in plan["frontier"]]
        out[f"cmtf|N={N},depth={depth}"] = ("cmtf", f"N={N},depth={depth}", cm_rank)
    return out


def evaluate(tasks, cfgs, pools, R: Ranker):
    rows = []
    for pname, pool in pools.items():
        for name, (meth, lab, f) in cfgs.items():
            for t in tasks:
                r = f(t, pool)
                if r is None:
                    continue
                g0 = next((x for grp in t["gold"] for x in grp if x in R.ret.contracts), None)
                conf = R.ret.contracts[g0].out.confidence if g0 else float("nan")
                rows.append({"pool": pname, "config": name, "method": meth, "label": lab, "id": t["id"],
                             "target": sorted(set().union(*t["gold"]))[0] if t["gold"] else t["id"],
                             "gold_conf": conf, **metrics(r, t["gold"])})
    return rows


def summarise(rows):
    out = defaultdict(dict)
    by = defaultdict(list)
    for r in rows:
        by[(r["pool"], r["config"])].append(r)
    for (pool, cfg), sel in by.items():
        m = {k: float(np.nanmean([x[k] for x in sel])) for k in ("hit1", "hit3", "hit5", "mrr10", "ndcg10")}
        m["n"] = len(sel)
        m["hit1_ci_target"] = fe.boot_ci([x["hit1"] for x in sel], clusters=[x["target"] for x in sel])
        bands = {"conf<0.70": lambda c: c < 0.70, "0.70<=conf<0.85": lambda c: 0.70 <= c < 0.85,
                 "conf>=0.85": lambda c: c >= 0.85}
        m["hit1_by_gold_confidence"] = {b: (float(np.mean([x["hit1"] for x in sel if f(x["gold_conf"])]))
                                            if any(f(x["gold_conf"]) for x in sel) else None,
                                            sum(1 for x in sel if f(x["gold_conf"]))) for b, f in bands.items()}
        out[pool][cfg] = m
    return out


def select(summ, cfg_names):
    best = {}
    order = {c: i for i, c in enumerate(cfg_names)}
    for cfg, m in summ["B1m"].items():
        meth = cfg.split("|")[0]
        key = (m["hit1"], m["mrr10"], -order[cfg])
        if meth not in best or key > best[meth][0]:
            best[meth] = (key, cfg)
    return {meth: v[1] for meth, v in best.items()}


def main() -> None:
    w = M.World()
    R = Ranker(w)
    dev, sample = fe.tasks_dev(), fe.tasks_e8_sample()
    exclude = {t["query"] for t in dev + sample}           # COLT never trains on dev or test queries
    cfgs = configs(R, w, {}, exclude)
    pp_ids = sorted({t.id for t in fe.raw() if t.source == "MCPToolBench++"}
                    | {g for t in fe.tasks_pp_all() for grp in t["gold"] for g in grp})
    B1 = [t for t in pp_ids if t in w.ret.pos]
    pools = {"B1": B1, "B1m": list(w.pool)}
    if SPLIT == "dev":
        rows = evaluate(dev, cfgs, pools, R)
        summ = summarise(rows)
        chosen = select(summ, list(cfgs))
        fe.save("R2_X3_dev", {"summary": summ, "selected": chosen, "n_tasks": len(dev),
                              "grid_sizes": {m: sum(1 for c in cfgs.values() if c[0] == m)
                                             for m in sorted({c[0] for c in cfgs.values()})}},
                "MEASURED (benchmark gold) on the development prompts only; selection rule fixed in the docstring",
                raw=fe.save_raw("R2_X3_dev", rows))
        for m, c in chosen.items():
            print(f"{m:10s} selected {c:32s} dev B1m Hit@1 {summ['B1m'][c]['hit1']:.3f}  B1 {summ['B1'][c]['hit1']:.3f}")
        for v in ("A", "B", "C", "D", "E", "F", "F2", "G70", "G85", "W50", "W25", "I", "J", "IJ"):
            s = summ["B1m"][f"pamcp|{v}"]
            print(f"pamcp|{v:4s} B1m hit1 {s['hit1']:.3f} mrr {s['mrr10']:.3f} ndcg {s['ndcg10']:.3f}  "
                  f"B1 hit1 {summ['B1'][f'pamcp|{v}']['hit1']:.3f}")
    else:
        sel = json.load(open(SEL_PATH))["selected"]
        keep = {c: cfgs[c] for c in sel.values()} | {c: cfgs[c] for c in cfgs if c.startswith("pamcp|")}
        rows = evaluate(sample, keep, pools, R)
        summ = summarise(rows)
        fe.save("R2_X3_test", {"summary": summ, "selected_on_dev": sel, "n_tasks": len(sample)},
                "MEASURED (benchmark gold) on the 300-query test sample with dev-selected configurations",
                raw=fe.save_raw("R2_X3_test", rows))
        for c in keep:
            print(f"{c:32s} test B1m Hit@1 {summ['B1m'][c]['hit1']:.3f}")


if __name__ == "__main__":
    main()
