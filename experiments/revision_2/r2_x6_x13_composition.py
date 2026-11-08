"""Revision 2, X6 (QoS-driven composition) and review Major 13 (optimality on diverse instances).

Exact optima come from an integer program solved by SciPy/HiGHS, written independently of the engine's
search: binary x_t; minimise sum c_t x_t; every goal covered by a selected producer; every required intermediate
type of a selected tool produced by a selected tool or available from the prompt; forbidden pairs excluded.
Instances are acyclic (producers of level-l types consume only lower levels), so this program is exact.

X13 instance families vary: alternatives per type, arity, depth, conflict density, tools serving several goals,
infeasible instances (a goal type nobody produces). For each instance: engine exact regime (branch and bound,
20,000-node budget), engine greedy regime, ILP over the engine's candidate set (search optimality) and ILP over all
tools (end-to-end, including retrieval truncation). Costs are the engine's Eq. (6) values on the candidate set.

X6: roles with interchangeable tools of differentiated price, latency and failure rate; the engine's choice under
weight settings and utility floors is compared with the exact Pareto front over (price, latency, reliability)
obtained by enumeration, and with the weighted-sum optimum in raw units.
Evidence class: SYNTHETIC instances; MEASURED solver outputs and latencies.
"""
from __future__ import annotations

import copy
import itertools
import random
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402
from taas.composer import ComposerConfig, CostModel  # noqa: E402
from taas.contracts import QoS, make_contract  # noqa: E402
from taas.engine import DiscoveryEngine, EngineConfig  # noqa: E402
from taas.goals import parse_goal_spec  # noqa: E402
from taas.policy import Policy  # noqa: E402

POL = Policy.make("p", required=(), allowed=("read(*)",), lmin=0.0, forbidden_pairs=())


# ------------------------------------------------------------------------------------------------ instances
def instance(goals: int, alts: int, depth: int, arity: int, conflicts: float, shared: float, infeasible: bool,
             seed: int):
    """Types t{level}_{j}; goals ask for level-`depth` types; a producer of a level-l type consumes `arity`
    types of level l-1 (level 0 = prompt input)."""
    rng = random.Random(seed)
    width = max(2, goals)
    cs, prod = [], {}
    for lvl in range(1, depth + 1):
        for j in range(width):
            ty = f"record:t{lvl}_{j}"
            for a in range(alts):
                ins = {"q": "query"} if lvl == 1 else {f"x{i}": f"record:t{lvl - 1}_{rng.randrange(width)}"
                                                       for i in range(arity)}
                name = f"p{a}::make_t{lvl}_{j}"
                c = make_contract(name, ins, ty, ["read(local)"], "obs", tool_class="retrieve",
                                  description=f"produce t{lvl}_{j}",
                                  qos=QoS(rng.uniform(0.05, 1.0), rng.uniform(0.05, 1.0), 0.01))
                cs.append(c)
                prod.setdefault(ty, []).append(name)
    if shared > 0:   # multi-output tools: one tool also produces a second goal type (as a second contract head)
        for j in range(width - 1):
            if rng.random() < shared:
                ty2 = f"record:t{depth}_{j + 1}"
                name = f"multi::make_t{depth}_{j}_{j + 1}"
                c = make_contract(name, {"q": "query"} if depth == 1 else {"x0": f"record:t{depth - 1}_{j}"}, ty2,
                                  ["read(local)"], "obs", tool_class="retrieve", description=f"produce t{depth}_{j + 1}",
                                  qos=QoS(rng.uniform(0.05, 0.5), rng.uniform(0.05, 0.5), 0.01))
                cs.append(c)
                prod.setdefault(ty2, []).append(name)
    gtypes = [f"record:t{depth}_{j}" for j in rng.sample(range(width), goals)]
    if infeasible:
        gtypes[0] = f"record:t{depth}_missing"
    goals_l = [{"id": f"g{i}", "desc": f"produce {t.split(':')[1]}", "class": "retrieve", "in": ["query"], "out": t,
                "eff": [], "sigma": "data", "n": 1} for i, t in enumerate(gtypes)]
    names = [c.tool for c in cs]
    forb = set()
    for a, b in itertools.combinations(names, 2):
        if rng.random() < conflicts:
            forb.add((a, b))
    return cs, goals_l, forb


def run_engine(cs, goals, forb, regime):
    from taas.hypergraph import Hypergraph
    cfg = EngineConfig(ComposerConfig(n_max=10 ** 6 if regime == "exact" else 0, relevance=0.0, K=50), refine_k=0)
    eng = DiscoveryEngine(cs, fe.profile("sonnet"), cfg=cfg, pair_policy=POL)
    eng.H.admin_forbidden = {tuple(sorted(p)): "conflict" for p in forb}
    eng.H.rebuild_pairs(POL)
    spec = parse_goal_spec({"id": "x", "prompt_inputs": ["query"], "goals": copy.deepcopy(goals)})
    t0 = time.perf_counter()
    r = eng.discover(spec, POL)
    return eng, r, time.perf_counter() - t0, cfg.composer


def ilp(cs, goals, forb, cost, allowed):
    """Exact minimum-cost toolkit over `allowed` tools (None if infeasible)."""
    T = [c for c in cs if c.tool in allowed]
    if not T:
        return None, 0.0
    idx = {c.tool: i for i, c in enumerate(T)}
    prod = {}
    for c in T:
        prod.setdefault(str(c.head).replace("[]", ""), []).append(idx[c.tool])
    rows, lo, hi = [], [], []
    n = len(T)
    for g in goals:
        r = np.zeros(n)
        for i in prod.get(g["out"], []):
            r[i] = 1
        rows.append(r); lo.append(1); hi.append(np.inf)
    for c in T:
        for a in c.args:
            if not a.required or a.type.kind == "query":
                continue
            r = np.zeros(n)
            r[idx[c.tool]] = -1
            for i in prod.get(str(a.type).replace("[]", ""), []):
                r[i] = 1
            rows.append(r); lo.append(0); hi.append(np.inf)
    for a, b in forb:
        if a in idx and b in idx:
            r = np.zeros(n)
            r[idx[a]] = r[idx[b]] = 1
            rows.append(r); lo.append(-np.inf); hi.append(1)
    c_vec = np.array([cost(c.tool) for c in T])
    t0 = time.perf_counter()
    res = milp(c_vec, constraints=LinearConstraint(np.array(rows), lo, hi), integrality=np.ones(n),
               bounds=Bounds(0, 1))
    dt = time.perf_counter() - t0
    if res.status != 0 or res.x is None:
        return None, dt
    return float(c_vec @ np.round(res.x)), dt


FAMILIES = {   # name -> instance parameters
    "base": dict(goals=3, alts=2, depth=2, arity=1, conflicts=0.0, shared=0.0, infeasible=False),
    "dense_alternatives": dict(goals=3, alts=6, depth=2, arity=1, conflicts=0.0, shared=0.0, infeasible=False),
    "deep": dict(goals=3, alts=2, depth=3, arity=1, conflicts=0.0, shared=0.0, infeasible=False),
    "arity2": dict(goals=3, alts=2, depth=2, arity=2, conflicts=0.0, shared=0.0, infeasible=False),
    "conflicts": dict(goals=3, alts=3, depth=2, arity=1, conflicts=0.05, shared=0.0, infeasible=False),
    "shared_tools": dict(goals=4, alts=2, depth=2, arity=1, conflicts=0.0, shared=0.7, infeasible=False),
    "more_goals": dict(goals=6, alts=2, depth=2, arity=1, conflicts=0.0, shared=0.0, infeasible=False),
    "infeasible": dict(goals=3, alts=2, depth=2, arity=1, conflicts=0.0, shared=0.0, infeasible=True),
}


def x13(seeds: int = 10) -> tuple[dict, list]:
    out, raw = {}, []
    for fam, p in FAMILIES.items():
        rows = []
        for sd in range(seeds):
            cs, goals, forb = instance(**p, seed=1000 * hash(fam) % 9973 + sd)
            eng, rx, tx, ccfg = run_engine(cs, goals, forb, "exact")
            _, rg, tg, _ = run_engine(cs, goals, forb, "greedy")
            cands = rx.compose.candidates or []
            cm = CostModel(eng.H, cands or [c.tool for c in cs], ccfg)
            cm_all = CostModel(eng.H, [c.tool for c in cs], ccfg)
            opt_c, t_ilp = ilp(cs, goals, forb, cm, set(cands)) if cands else (None, 0.0)
            opt_all, _ = ilp(cs, goals, forb, cm_all, {c.tool for c in cs})
            ex = cm.total(rx.toolkit) if rx.toolkit is not None and cands else None
            gr = cm.total(rg.toolkit) if rg.toolkit is not None and cands else None
            row = {"family": fam, "seed": sd, "tools": len(cs), "candidates": len(cands),
                   "exact_regime": rx.compose.regime, "exact_cost": ex, "greedy_cost": gr, "ilp_candidates": opt_c,
                   "ilp_all_cost_all_normalised": opt_all,
                   "exact_all_cost": cm_all.total(rx.toolkit) if rx.toolkit is not None else None,
                   "exact_abstained": rx.toolkit is None, "greedy_abstained": rg.toolkit is None,
                   "ilp_infeasible": opt_all is None, "exact_ms": 1000 * tx, "greedy_ms": 1000 * tg,
                   "ilp_ms": 1000 * t_ilp, "chi": rx.counterexample.kind if rx.counterexample else ""}
            rows.append(row)
        raw += rows
        ok = [r for r in rows if r["exact_cost"] is not None and r["ilp_candidates"] is not None]
        solved = [r for r in ok if "budget" not in r["exact_regime"]]
        out[fam] = {
            "instances": len(rows),
            "ilp_infeasible": sum(r["ilp_infeasible"] for r in rows),
            "engine_abstained_exact": sum(r["exact_abstained"] for r in rows),
            "abstention_agrees_with_ilp": sum(r["exact_abstained"] == r["ilp_infeasible"] for r in rows),
            "exact_budget_exhausted": sum("budget" in r["exact_regime"] for r in rows),
            "exact_equals_ilp_on_candidates": sum(abs(r["exact_cost"] - r["ilp_candidates"]) < 1e-6 for r in solved),
            "exact_solved": len(solved),
            "greedy_over_ilp_mean": float(np.mean([r["greedy_cost"] / r["ilp_candidates"] for r in ok
                                                   if r["greedy_cost"] is not None])) if ok else None,
            "greedy_over_ilp_max": float(np.max([r["greedy_cost"] / r["ilp_candidates"] for r in ok
                                                 if r["greedy_cost"] is not None])) if ok else None,
            "exact_over_ilp_all_mean": float(np.mean([r["exact_all_cost"] / r["ilp_all_cost_all_normalised"]
                                                      for r in rows if r["exact_all_cost"] is not None
                                                      and r["ilp_all_cost_all_normalised"]])) if any(
                r["exact_all_cost"] is not None and r["ilp_all_cost_all_normalised"] for r in rows) else None,
            "exact_ms_p50": float(np.median([r["exact_ms"] for r in rows])),
            "exact_ms_p95": float(np.percentile([r["exact_ms"] for r in rows], 95)),
            "greedy_ms_p50": float(np.median([r["greedy_ms"] for r in rows])),
            "ilp_ms_p50": float(np.median([r["ilp_ms"] for r in rows])),
        }
        print("X13", fam, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[fam].items()})
    return out, raw


# ------------------------------------------------------------------------------------------------ X6
def qos_instance(roles: int, alts: int, seed: int):
    rng = random.Random(seed)
    cs = []
    for r in range(roles):
        for a in range(alts):
            price = rng.choice([0.0, 0.001, 0.01, 0.05]) * rng.uniform(0.5, 1.5)
            lat = rng.lognormvariate(-1.0, 0.8)
            fail = rng.choice([0.001, 0.01, 0.05, 0.15])
            cs.append(make_contract(f"vendor{a}::role{r}", {"q": "query"}, f"record:role{r}", ["read(web)"], "obs",
                                    tool_class="retrieve", description=f"role {r} provider {a}",
                                    qos=QoS(price, lat, fail)))
    goals = [{"id": f"g{r}", "desc": f"obtain role {r}", "class": "retrieve", "in": ["query"],
              "out": f"record:role{r}", "eff": [], "sigma": "data", "n": 1} for r in range(roles)]
    return cs, goals


def x6(seeds: int = 10) -> tuple[dict, list]:
    weights = {"default (all 0.5)": {}, "price only": dict(beta=0, gamma=0, delta=0, eta=1, zeta=0),
               "latency only": dict(beta=0, gamma=0, delta=0, eta=0, zeta=1),
               "price+latency": dict(beta=0, gamma=0, delta=0, eta=1, zeta=1)}
    floors = (0.0, 0.8, 0.9)
    raw, out = [], {}
    pol = Policy.make("p", required=(), allowed=("read(*)", "egress(*)"), lmin=0.0)
    for wname, wv in weights.items():
        for umin in floors:
            rows = []
            for sd in range(seeds):
                cs, goals = qos_instance(roles=4, alts=4, seed=sd)
                C = {c.tool: c for c in cs}
                ccfg = ComposerConfig(relevance=0.0, K=10, u_min=umin, **wv)
                eng = DiscoveryEngine(cs, fe.profile("sonnet"), cfg=EngineConfig(ccfg, refine_k=0), pair_policy=pol)
                spec = parse_goal_spec({"id": "x", "prompt_inputs": ["query"], "goals": copy.deepcopy(goals)})
                r = eng.discover(spec, pol)
                # exact enumeration of all one-provider-per-role toolkits
                by_role = [[c.tool for c in cs if c.tool.endswith(f"::role{i}")] for i in range(4)]
                allk = []
                for combo in itertools.product(*by_role):
                    price = sum(C[t].qos.price for t in combo)
                    lat = sum(C[t].qos.latency for t in combo)
                    rel = float(np.prod([1 - C[t].qos.fail for t in combo]))
                    allk.append((combo, price, lat, rel))
                feas = [k for k in allk if k[3] >= umin]

                def dominated(k, pool):
                    return any(o[1] <= k[1] and o[2] <= k[2] and o[3] >= k[3] and (o[1], o[2], o[3]) != (k[1], k[2], k[3])
                               for o in pool)
                front = [k for k in feas if not dominated(k, feas)]
                if r.toolkit is None:
                    rows.append({"weights": wname, "u_min": umin, "seed": sd, "abstained": True,
                                 "feasible_exists": bool(feas)})
                    continue
                K = tuple(sorted(r.toolkit))
                me = next(k for k in allk if tuple(sorted(k[0])) == K)
                eta, zeta = wv.get("eta", 0.5), wv.get("zeta", 0.5)
                ws = lambda k: eta * k[1] + zeta * k[2]
                best_ws = min(feas, key=ws) if feas else None
                rows.append({"weights": wname, "u_min": umin, "seed": sd, "abstained": False,
                             "feasible_exists": bool(feas), "pareto_optimal": not dominated(me, feas),
                             "front_size": len(front), "price": me[1], "latency": me[2], "reliability": me[3],
                             "meets_floor": me[3] >= umin,
                             "raw_weighted_regret": (ws(me) / ws(best_ws) - 1) if best_ws and ws(best_ws) > 0 else 0.0,
                             "cheapest_price": min(k[1] for k in feas) if feas else None,
                             "fastest_latency": min(k[2] for k in feas) if feas else None})
            raw += rows
            sel = [x for x in rows if not x["abstained"]]
            out[f"{wname}|u_min={umin}"] = {
                "instances": len(rows), "abstained": sum(x["abstained"] for x in rows),
                "abstained_but_feasible": sum(x["abstained"] and x["feasible_exists"] for x in rows),
                "pareto_optimal_share": float(np.mean([x["pareto_optimal"] for x in sel])) if sel else None,
                "meets_floor_share": float(np.mean([x["meets_floor"] for x in sel])) if sel else None,
                "mean_price": float(np.mean([x["price"] for x in sel])) if sel else None,
                "mean_latency": float(np.mean([x["latency"] for x in sel])) if sel else None,
                "mean_reliability": float(np.mean([x["reliability"] for x in sel])) if sel else None,
                "raw_weighted_regret_mean": float(np.mean([x["raw_weighted_regret"] for x in sel])) if sel else None}
            print("X6", wname, umin, {k: (round(v, 3) if isinstance(v, float) else v)
                                      for k, v in out[f"{wname}|u_min={umin}"].items()})
    return out, raw


def main() -> None:
    r13, raw13 = x13()
    r6, raw6 = x6()
    fe.save("R2_X6_X13_composition", {"x13_optimality": r13, "x6_qos": r6},
            "SYNTHETIC instances; MEASURED solver outputs (engine exact and greedy regimes, HiGHS ILP, enumeration)",
            config={"families": FAMILIES, "seeds": 10, "qos_roles": 4, "qos_alternatives": 4, "node_budget": 20000},
            raw=fe.save_raw("R2_X6_X13_composition", [{"x13": r} for r in raw13] + [{"x6": r} for r in raw6]))


if __name__ == "__main__":
    main()
