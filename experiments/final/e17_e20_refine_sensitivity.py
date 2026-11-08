"""E17 counterexample-guided refinement (LLM-free repair operators; assistant-role variants not run) and E20
sensitivity to the cost weights of Eq. (6) and the utility floor u_min.

Tasks: 95 LiveMCPBench test + 60 MCPToolBench++ development prompts under each task's least-privilege policy.
"""
from __future__ import annotations

import copy
from collections import Counter, defaultdict

import sys

import fe
import methods as M
import set_evaluator as SE
from taas.composer import ComposerConfig
from taas.engine import DiscoveryEngine, EngineConfig


SPLIT = "test" if "--split" in sys.argv and sys.argv[sys.argv.index("--split") + 1] == "test" else "all"
SUFFIX = "_test" if SPLIT == "test" else ""


def tasks_specs():
    """All 155 tasks (paper), or with --split test only the 95 LiveMCPBench tasks (Revision 2: the 60 development
    prompts selected K and w_rel)."""
    out = []
    for t in fe.tasks_live() + ([] if SPLIT == "test" else fe.tasks_dev()):
        spec, rec = fe.spec_for(t)
        if spec is not None:
            pol, need = M.least_privilege(rec)
            out.append((t, spec, rec, pol, need))
    return out


RAW17: list[dict] = []
RAW20: list[dict] = []


def e17(ts) -> dict:
    w = M.World()
    cs = w.cs["verified"]
    res = {}
    first = {}
    for budget in ("K=5", "K=1 (induced chi1)"):
        Kb = 5 if budget == "K=5" else 1
        for k in (0, 1, 2, 3, 5):
            eng = DiscoveryEngine(cs, w.prof, cfg=EngineConfig(ComposerConfig(K=Kb), refine_k=k),
                                  pair_policy=M.open_policy())
            rows = []
            for t, spec, rec, pol, need in ts:
                r = eng.discover(copy.deepcopy(spec), pol)
                if k == 0:
                    first[(budget, t["id"])] = r.counterexample.kind if r.counterexample else "valid"
                rows.append({"id": t["id"], "valid": r.toolkit is not None,
                             "steps": len(r.trace.steps) if r.trace else 0,
                             "outcome": r.trace.outcome if r.trace else "", "tokens": w.tokens(r.toolkit or [])})
                RAW17.append({"budget": budget, "k": k, **rows[-1], "first_chi": first[(budget, t["id"])],
                              "final_chi": r.counterexample.kind if r.counterexample else "",
                              "ops": [st.get("op") for st in (r.trace.steps if r.trace else [])],
                              "toolkit": r.toolkit, "time_s": r.time_s})
            by_chi = defaultdict(list)
            for r in rows:
                by_chi[first[(budget, r["id"])]].append(r)
            res[f"{budget}|k={k}"] = {
                "valid_rate": sum(r["valid"] for r in rows) / len(rows),
                "abstain_rate": 1 - sum(r["valid"] for r in rows) / len(rows),
                "repair_success_by_chi": {c: sum(r["valid"] for r in v) / len(v) for c, v in by_chi.items()
                                          if c != "valid"},
                "n_by_chi": {c: len(v) for c, v in by_chi.items()},
                "mean_iterations_repaired": fe.nanmean(r["steps"] for r in rows
                                                       if r["valid"] and first[(budget, r["id"])] != "valid"),
                "mean_tokens_valid": fe.nanmean(r["tokens"] for r in rows if r["valid"])}
            print("E17", budget, k, round(res[f"{budget}|k={k}"]["valid_rate"], 3), res[f"{budget}|k={k}"]["n_by_chi"])
    # scenario with a flow counterexample (Fig. 3 revenue), repaired by the chi5 split
    from taas.scenarios import revenue_policy, revenue_registry, revenue_spec
    from taas.goals import parse_goal_spec
    for k in (0, 3):
        eng = DiscoveryEngine(list(revenue_registry()), w.prof, cfg=EngineConfig(refine_k=k),
                              pair_policy=revenue_policy())
        r = eng.discover(parse_goal_spec(copy.deepcopy(revenue_spec()), "revenue"), revenue_policy())
        res[f"revenue_scenario|k={k}"] = {"toolkit": r.toolkit, "chi": r.counterexample.kind if r.counterexample else "",
                                          "outcome": r.trace.outcome if r.trace else ""}
    return res


CUR = ["default"]


def e20(ts) -> dict:
    w = M.World()
    eng = DiscoveryEngine(w.cs["verified"], w.prof, cfg=EngineConfig(ComposerConfig()), pair_policy=M.open_policy())
    cfg = eng.composer.cfg
    B = fe.labels_B_raw()
    default = {f: getattr(cfg, f) for f in ("beta", "gamma", "delta", "eta", "zeta", "u_min")}
    CUR[0] = "default"

    def run():
        out = {}
        for t, spec, rec, pol, need in ts:
            r = eng.discover(copy.deepcopy(spec), pol)
            out[t["id"]] = r.toolkit
            RAW20.append({"setting": CUR[0], "id": t["id"], "toolkit": r.toolkit,
                          "chi": r.counterexample.kind if r.counterexample else ""})
        return out

    def stats(K_by, ref):
        jac, rec, price, lat, forb, ab = [], [], [], [], [], 0
        for t, spec, rec_, pol, need in ts:
            K = K_by[t["id"]]
            R = ref[t["id"]]
            if K is None:
                ab += 1
                continue
            a, b = set(K), set(R or [])
            jac.append(1.0 if not a and not b else len(a & b) / len(a | b))
            if t["gold"]:
                rec.append(fe.group_recall(K, t["gold"]))
            price.append(sum(eng.H.contracts[x].qos.price for x in K))
            lat.append(sum(eng.H.contracts[x].qos.latency for x in K))
            forb.append(SE.evaluate(K, rec_, need)["forbidden_tools"])
        return {"jaccard_vs_default": fe.nanmean(jac), "changed_share": sum(1 for j in jac if j < 1) / max(1, len(jac)),
                "recall": fe.nanmean(rec), "price": fe.nanmean(price), "latency": fe.nanmean(lat),
                "forbidden_tools": fe.nanmean(forb), "abstain_rate": ab / len(ts)}
    ref = run()
    res = {"default": stats(ref, ref) | {"config": default}}
    for f in ("beta", "gamma", "delta", "eta", "zeta"):
        for v in (0.0, 0.25, 1.0):
            setattr(cfg, f, v)
            CUR[0] = f"{f}={v}"
            res[f"{f}={v}"] = stats(run(), ref)
            setattr(cfg, f, default[f])
    for v in (0.4, 0.6, 0.8):
        cfg.u_min = v
        CUR[0] = f"u_min={v}"
        res[f"u_min={v}"] = stats(run(), ref)
        cfg.u_min = default["u_min"]
    for b in (0.0, 0.25, 1.0):
        for g in (0.0, 0.25, 1.0):
            cfg.beta, cfg.gamma = b, g
            CUR[0] = f"beta={b},gamma={g}"
            res[f"beta={b},gamma={g}"] = stats(run(), ref)
    cfg.beta, cfg.gamma = default["beta"], default["gamma"]
    return res


def main() -> None:
    ts = tasks_specs()
    r17 = e17(ts)
    fe.save("E17_refinement" + SUFFIX, {"results": r17, "split": SPLIT}, "MEASURED (engine; LLM-free repairs); assistant-role variants not run",
            config={"tasks": len(ts), "policy": "least privilege", "k": [0, 1, 2, 3, 5], "budgets": ["K=5", "K=1"]},
            raw=fe.save_raw("E17_refinement" + SUFFIX, RAW17))
    r20 = e20(ts)
    fe.save("E20_sensitivity" + SUFFIX, {"results": r20, "split": SPLIT}, "MEASURED (toolkits, recall vs gold); LABELLED (forbidden tools, B)",
            config={"tasks": len(ts), "weights": [0.0, 0.25, 0.5, 1.0], "u_min": [0.4, 0.5, 0.6, 0.8],
                    "joint": "beta x gamma"}, raw=fe.save_raw("E20_sensitivity" + SUFFIX, RAW20))
    for k, v in r20.items():
        print("E20", k, {x: round(y, 3) for x, y in v.items() if isinstance(y, float)})


if __name__ == "__main__":
    main()
