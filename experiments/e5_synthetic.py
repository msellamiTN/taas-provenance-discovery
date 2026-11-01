"""E5 — RQ3 on controlled synthetic typed registries: set-level compatibility, backward closure over
intermediate types, tool sharing, optimality of the exact regime and quality of the greedy regime.

Each task is a hidden typed chain query:dX → T1 → … → TL plus a branch served by a shared tool.
Only the final type and one intermediate are named as goals; the other intermediates must be found
by backward closure. Distractors per step: type-incompatible (wrong tail), ineligible (lexical
evidence only), forbidden effect (delete), costlier QoS twin, and a lexically closer but wrongly
typed tool. Validity is graded by an independent checker over the generator's ground truth, and the
optimum by brute force over the eligible pool.
"""
from __future__ import annotations

import itertools
import random
import time

from common import SEEDS, banner, mean_ci, save

from taas.composer import ComposerConfig, CostModel
from taas.contracts import QoS, make_contract
from taas.engine import DiscoveryEngine, EngineConfig
from taas.goals import parse_goal_spec
from taas.model_profile import ModelProfile
from taas.policy import Policy
from taas.retrieval import HybridRetriever
from taas import baselines
from taas.types import parse_type, subtype

WORDS = ["orbit", "harvest", "ledger", "glacier", "pixel", "tariff", "voyage", "quartz", "meadow", "cipher",
         "lantern", "anchor", "summit", "canyon", "fable", "ember", "nectar", "prism", "relay", "timber"]


def gen_task(seed: int, L: int = 3, n_distract: int = 3):
    rng = random.Random(seed)
    doms = rng.sample(WORDS, L + 2)
    kinds = ["record", "table", "document"]
    T = [f"query:{doms[0]}"] + [f"{rng.choice(kinds)}:{doms[i + 1]}{'[]' if rng.random() < .3 else ''}" for i in range(L)]
    cs, truth_ok = [], set()
    for i in range(L):
        dw = doms[i + 1]
        good = make_contract(f"srv{i}::make_{dw}", {"x": T[i]}, T[i + 1], ["read(local)"], "obs",
                             tool_class="convert_format", description=f"produce {dw} from {doms[i]}",
                             qos=QoS(rng.uniform(0, .3), rng.uniform(.2, .5), .01))
        cs.append(good)
        truth_ok.add(good.tool)
        for j in range(n_distract):
            kind = j % 5
            if kind == 0:   # incompatible tail: needs a type nobody produces
                cs.append(make_contract(f"alt{i}{j}::make_{dw}_v{j}", {"x": f"record:unobtainable{j}"}, T[i + 1],
                                        ["read(local)"], "obs", description=f"produce {dw} quickly"))
            elif kind == 1:  # ineligible: only lexical evidence
                cs.append(make_contract(f"lex{i}{j}::make_{dw}_lx", {"x": T[i]}, T[i + 1], ["read(local)"], "lex",
                                        description=f"produce {dw} from {doms[i]} fast"))
            elif kind == 2:  # forbidden effect
                cs.append(make_contract(f"del{i}{j}::make_{dw}_rm", {"x": T[i]}, T[i + 1],
                                        ["read(local)", "delete(*)"], "obs", description=f"produce {dw} and clean up"))
            elif kind == 3:  # costlier twin (valid but dominated)
                twin = make_contract(f"twin{i}{j}::make_{dw}_pro", {"x": T[i]}, T[i + 1], ["read(local)"], "obs",
                                     tool_class="convert_format", description=f"produce {dw} from {doms[i]} premium",
                                     qos=QoS(rng.uniform(.6, 1.0), rng.uniform(.6, 1.0), .02))
                cs.append(twin)
                truth_ok.add(twin.tool)
            else:            # lexically closer, wrong output type
                cs.append(make_contract(f"lure{i}{j}::produce_{dw}_{doms[i]}", {"x": T[i]},
                                        f"text:{doms[-1]}", ["read(local)"], "obs",
                                        description=f"produce {dw} from {doms[i]} {dw} {dw}"))
    # shared tool: one tool serves the final goal and a side goal of a supertype
    final = parse_type(T[-1])
    spec = {"id": f"syn{seed}", "prompt_inputs": ["text", T[0]], "goals": [
        {"id": "gm", "class": "convert_format", "in": [T[0]], "out": T[L // 2 + 1] if L > 1 else T[1],
         "sigma": "data", "desc": f"produce {doms[L // 2 + 1]}"},
        {"id": "gf", "class": "convert_format", "in": [T[0]], "out": T[-1], "sigma": "data",
         "desc": f"produce {doms[L]}"},
        {"id": "gs", "class": "convert_format", "in": [T[0]], "out": f"{final.kind}" + ("[]" if final.collection else ""),
         "sigma": "data", "desc": f"any {final.kind}"},
    ]}
    return cs, spec, T, truth_ok


def checker_valid(K, cs_by, T, policy: Policy) -> bool:
    """Independent ground-truth check: chain types reachable from the prompt using K, every tool
    eligible (obs+ evidence) and effects within A."""
    R = {parse_type(T[0]), parse_type("text")}
    changed = True
    while changed:
        changed = False
        for t in K:
            c = cs_by[t]
            if all(any(subtype(s, th) for s in R) for th in c.tail) and c.head not in R:
                R.add(c.head)
                changed = True
    ok_types = any(subtype(s, parse_type(T[-1])) for s in R) and any(subtype(s, parse_type(T[len(T) // 2])) for s in R)
    ok_eff = all(all(e.cls == "read" for e in cs_by[t].eff) for t in K)
    ok_ev = all(cs_by[t].eff_record.ptype in ("obs", "att") for t in K)
    return ok_types and ok_eff and ok_ev


def brute_optimum(eng, spec_d, policy, cs_by, T, pool):
    goals = parse_goal_spec(spec_d).goals
    cm = CostModel(eng.H, pool, eng.cfg.composer)
    best = None
    for r in range(1, min(len(pool), len(T) + 1) + 1):
        for K in itertools.combinations(pool, r):
            if checker_valid(K, cs_by, T, policy):
                c = cm.total(K)
                if best is None or c < best[0]:
                    best = (c, K)
        if best is not None and r >= len(T) - 1:
            break
    return best, cm


def main(Ls=(2, 3, 4), dists=(3, 5), seeds=tuple(range(8))) -> dict:
    banner("E5 / RQ3: synthetic typed registries — validity, optimality, closure and sharing "
           "(graded by an independent checker; optimum by brute force)")
    prof = ModelProfile("synthetic", 0.9, {}, strict=True)
    pol = Policy.make("syn", required={"no_delete"}, allowed=("read(*)",), lmin="obs")
    rows = []
    for L in Ls:
        for nd in dists:
            for s in seeds:
                cs, spec_d, T, truth_ok = gen_task(1000 * L + 10 * nd + s, L, nd)
                cs_by = {c.tool: c for c in cs}
                variants = {
                    "ours-exact": ComposerConfig(relevance=0.0, K=5),
                    "ours-greedy": ComposerConfig(relevance=0.0, K=5, n_max=0),
                    "ours-no-closure": ComposerConfig(relevance=0.0, K=5, depth=0),
                }
                for name, ccfg in variants.items():
                    eng = DiscoveryEngine(cs, prof, cfg=EngineConfig(ccfg, refine_k=0), pair_policy=pol)
                    t0 = time.perf_counter()
                    r = eng.discover(parse_goal_spec(spec_d), pol)
                    dt = time.perf_counter() - t0
                    K = r.toolkit or []
                    valid = bool(K) and checker_valid(K, cs_by, T, pol)
                    rows.append({"L": L, "nd": nd, "seed": s, "system": name, "valid": valid, "abstain": not K,
                                 "size": len(K), "time_s": dt, "cost": None, "K": K})
                eng = DiscoveryEngine(cs, prof, cfg=EngineConfig(ComposerConfig(relevance=0.0), refine_k=0),
                                      pair_policy=pol)
                pool = [c.tool for c in cs if c.eff_record.ptype in ("obs", "att")
                        and all(e.cls == "read" for e in c.eff)]
                best, cm = brute_optimum(eng, spec_d, pol, cs_by, T, pool)
                spec = parse_goal_spec(spec_d)
                for name, K in (("per-subtask", baselines.per_subtask(eng.retriever, spec, list(cs_by), 1)),):
                    rows.append({"L": L, "nd": nd, "seed": s, "system": name, "valid": checker_valid(K, cs_by, T, pol),
                                 "abstain": False, "size": len(K), "time_s": 0.0, "K": K})
                for r_ in rows[-4:]:
                    if r_["K"] and best is not None and all(t in cm.c for t in r_["K"]):
                        r_["cost"] = cm.total(r_["K"])
                        r_["opt_ratio"] = r_["cost"] / best[0] if r_["valid"] else None
                    r_["opt_size"] = len(best[1]) if best else None
    summary = {}
    for name in ("ours-exact", "ours-greedy", "ours-no-closure", "per-subtask"):
        sel = [r for r in rows if r["system"] == name]
        summary[name] = {"valid_rate": sum(r["valid"] for r in sel) / len(sel),
                         "abstain_rate": sum(r["abstain"] for r in sel) / len(sel),
                         "optimal_rate": sum(1 for r in sel if r.get("opt_ratio") is not None and r["opt_ratio"] <= 1 + 1e-9)
                         / len(sel),
                         "opt_ratio": mean_ci(r["opt_ratio"] for r in sel if r.get("opt_ratio") is not None),
                         "size": mean_ci(r["size"] for r in sel), "time_s": mean_ci(r["time_s"] for r in sel)}
        m = summary[name]
        print(f"{name:16s} valid={m['valid_rate']:.3f} optimal={m['optimal_rate']:.3f} "
              f"cost/opt={m['opt_ratio']['mean']:.3f} |K|={m['size']['mean']:.2f} abstain={m['abstain_rate']:.2f} "
              f"t={m['time_s']['mean'] * 1000:.1f}ms")
    for L in Ls:
        sel = [r for r in rows if r["system"] == "ours-exact" and r["L"] == L]
        print(f"  L={L}: exact valid={sum(r['valid'] for r in sel) / len(sel):.2f} "
              f"t={mean_ci(r['time_s'] for r in sel)['mean'] * 1000:.1f}ms")
    save("e5_synthetic", {"summary": summary, "rows": rows})
    return summary


if __name__ == "__main__":
    main()
