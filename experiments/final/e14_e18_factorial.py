"""E18 primary-mechanism ablation (2^3 factorial over G = capability gap, P = provenance-sound eligibility,
S = set-level reasoning and certification) with Shapley attribution and component leave-one-out, and E14
robustness to prompt injection (offline: reachable out-of-scope actions, description-borne and output-borne
exposure). Tasks: 95 LiveMCPBench test + 60 MCPToolBench++ development prompts. Policies: each task's least
privilege (read + the scoped writes its goals need) and strict read-only.
"""
from __future__ import annotations

import itertools
import random
from collections import defaultdict
from math import factorial

import numpy as np

import fe
import methods as M
import set_evaluator as SE
from taas.composer import ComposerConfig
from taas.engine import DiscoveryEngine, EngineConfig
from taas.simulation import ATTACKS, attack_success

ATTACK_NEED = {"destroy": "delete", "execute": "exec", "pay": "money", "tamper": "write"}
# Revision 2: the poisoning exposure is measured by scanning what each method shows the model (it used to be set
# to 0 for the sanitised cells). Canaries are planted in the description, the tool name and the argument keys.
CANARY = {"desc": "R2CANARYDESC", "name": "R2CANARYNAME", "arg": "R2CANARYARG"}


def poisoned(c):
    import copy as _copy
    from dataclasses import replace as _replace
    x = _copy.deepcopy(c)
    x.description = (x.description or "") + " " + CANARY["desc"]
    x.name = f"{CANARY['name']}_{x.name}"
    x.args = tuple(_replace(a, name=f"{CANARY['arg']}_{a.name}") for a in x.args)
    return x


def visible_json(K, C, bad, mode):
    """Serialised model-visible tool list for toolkit K: 'alias' (Revision 2 manifest), 'legacy' (sanitise only)
    or 'raw' (provider definitions as retrieved, the baselines' exposure)."""
    import json as _json
    from taas.manifest import alias_entry, sanitise
    cs = [poisoned(C[t]) if t in bad else C[t] for t in K if t in C]
    if mode == "alias":
        out = [alias_entry(c, f"tool_{i + 1:03d}")[0] for i, c in enumerate(cs)]
    elif mode == "legacy":
        out = [sanitise(c) for c in cs]
    else:
        out = [{"name": c.name, "description": c.description,
                "inputSchema": {"properties": {a.name: {"description": str(a.type)} for a in c.args}}} for c in cs]
    return _json.dumps(out)


def canary_hits(js: str) -> dict:
    return {f: CANARY[f] in js for f in CANARY}
CELLS = [(g, p, s) for g in (1, 0) for p in (1, 0) for s in (1, 0)]
CELL_NAME = {(1, 1, 1): "Full_PaMCP", (1, 1, 0): "PaMCP_NoCert", (1, 0, 1): "PaMCP_Declared",
             (0, 1, 1): "PaMCP_NoGap", (1, 0, 0): "G1_P0_S0", (0, 1, 0): "G0_P1_S0", (0, 0, 1): "G0_P0_S1",
             (0, 0, 0): "G0_P0_S0"}


def out_of_scope(need: set[str]) -> list[str]:
    out = []
    for a in ATTACKS:
        if a == "exfiltrate" or ATTACK_NEED.get(a) not in need:
            if a == "tamper" and need:
                continue
            out.append(a)
    return out


def output_borne(K, Bd) -> bool:
    """Toolkit reads content an attacker can control (remote/web results)."""
    return any(set(Bd.get(t, {}).get("classes") or []) & {"egress", "egress_any"} for t in K)


def aggregate(rows: list[dict]) -> tuple[dict, dict, dict, dict, int]:
    """Summaries, attack rates, factorial effects and per-method abstention for a subset of rows."""
    # ---------------------------------------------------------------- summaries
    metrics = ["size", "tokens", "manifest_tokens", "recall", "joint", "E_ok", "reach_any", "output_borne",
               "exploitable_output", "poison_shown_0.1", "poison_shown_0.3", "poison_raw_0.3",
               "poison_shown_desc_0.3", "poison_shown_name_0.3", "poison_shown_arg_0.3", "poison_shown_legacy_0.3",
               "abstain"]
    summ = fe.summarise(rows, ["policy", "method"], metrics)
    # attack-level rates with Wilson CIs (task x out-of-scope attack pairs)
    att = {}
    for pol in ("least_privilege", "read_only"):
        for m in sorted({r["method"] for r in rows}):
            sel = [r for r in rows if r["policy"] == pol and r["method"] == m]
            k, n = sum(r["reach"] for r in sel), sum(r["n_oos"] for r in sel)
            att[f"{pol}|{m}"] = {"k": k, "n": n, "rate": k / n if n else float("nan"), "ci": fe.wilson(k, n)}
    # factorial effects and Shapley values (least privilege, tasks where all eight cells exist)
    fac = {}
    for pol in ("least_privilege", "read_only"):
        by = defaultdict(dict)
        for r in rows:
            if r["policy"] == pol and r["method"] in CELL_NAME.values():
                by[r["id"]][r["method"]] = r
        ids = [i for i, d in by.items() if len(d) == 8]
        for m in ("recall", "size", "tokens", "joint", "reach_any", "E_ok"):
            v = {}
            for cell, name in CELL_NAME.items():
                v[cell] = [by[i][name][m] for i in ids]
            ok = [j for j in range(len(ids)) if all(not np.isnan(v[c][j]) for c in v)]

            def val(cell, j):
                return v[cell][j]
            eff = {}
            for f_idx, fname in enumerate("GPS"):
                d = []
                for j in ok:
                    hi = [val(c, j) for c in v if c[f_idx] == 1]
                    lo = [val(c, j) for c in v if c[f_idx] == 0]
                    d.append(np.mean(hi) - np.mean(lo))
                eff[f"main_{fname}"] = {"mean": float(np.mean(d)), "ci": fe.boot_ci(d), "p": fe.signflip(d)}
            for a, b in itertools.combinations(range(3), 2):
                d = []
                for j in ok:
                    s = 0.0
                    for c in v:
                        s += (1 if c[a] == c[b] else -1) * val(c, j)
                    d.append(s / 4)
                eff[f"interaction_{'GPS'[a]}{'GPS'[b]}"] = {"mean": float(np.mean(d)), "ci": fe.boot_ci(d),
                                                         "p": fe.signflip(d)}
            mean = {c: float(np.mean([val(c, j) for j in ok])) for c in v}
            shap = {}
            for i, fname in enumerate("GPS"):
                tot = 0.0
                for perm in itertools.permutations(range(3)):
                    cur = [0, 0, 0]
                    for x in perm:
                        before = mean[tuple(cur)]
                        cur[x] = 1
                        if x == i:
                            tot += mean[tuple(cur)] - before
                            break
                shap[fname] = tot / factorial(3)
            fac[f"{pol}|{m}"] = {"n": len(ok), "cell_means": {CELL_NAME[c]: mean[c] for c in mean}, "effects": eff,
                                 "shapley": shap, "full_minus_none": mean[(1, 1, 1)] - mean[(0, 0, 0)]}
    n_tasks = len({r["id"] for r in rows})
    per_method = {}
    for r in rows:
        k = f"{r['policy']}|{r['method']}"
        d = per_method.setdefault(k, {"n": 0, "abstain": 0, "certified": 0, "chi": {}})
        d["n"] += 1
        d["abstain"] += bool(r["abstain"])
        d["certified"] += bool(r["certified"])
        if r["chi"]:
            d["chi"][r["chi"]] = d["chi"].get(r["chi"], 0) + 1
    return summ, att, fac, per_method, n_tasks


def main() -> None:
    B = fe.labels_B()
    Bd = fe.labels_B_raw()
    tasks = [t for t in fe.tasks_live() + fe.tasks_dev()]
    live_ids = {t["id"] for t in fe.tasks_live()}
    w = M.World()
    mz, ts = M.MCPZero(w), M.ToolScope(w)
    colt = M.COLT(w, {t["query"] for t in fe.tasks_dev() + fe.tasks_e8_sample()})
    cm = M.CMTF(w)
    comps = {"no_closure": dict(depth=0), "derivation_flow": dict(conservative_flow=False),
             "no_utility_floor": dict(u_min=0.0), "no_relevance_term": dict(relevance=0.0)}
    comp_eng = {k: DiscoveryEngine(w.cs["verified"], w.prof, cfg=EngineConfig(ComposerConfig(**v)),
                                   pair_policy=M.open_policy()) for k, v in comps.items()}
    comp_eng["no_refinement"] = DiscoveryEngine(w.cs["verified"], w.prof, cfg=EngineConfig(ComposerConfig(), refine_k=0),
                                                pair_policy=M.open_policy())
    C_by_id = {c.tool: c for c in w.cs["verified"]}
    rng_poison = {(dens, sd): set(random.Random(1000 * sd + int(dens * 100)).sample(w.pool, round(dens * len(w.pool))))
                  for dens in (0.1, 0.3) for sd in range(5)}
    rows = []
    for t in tasks:
        spec, rec = fe.spec_for(t)
        if spec is None:
            continue
        for pname in ("least_privilege", "read_only"):
            r0 = rec if pname == "least_privilege" else {**rec, "goals": [{**g, "eff": []} for g in rec["goals"]]}
            pol1, need = M.least_privilege(r0)
            pol0, _ = M.least_privilege(r0, declared=True)
            elig1 = set(w.eligible(1, pol1))
            res = {}
            for (G, P, S) in CELLS:
                r = w.pamcp(G, P, S, spec, rec, pol1 if P else pol0)
                res[CELL_NAME[(G, P, S)]] = (r["K"], r["abstain"], r.get("manifest_tokens"),
                                             r.get("valid") if S else None, r.get("chi", ""))
            if pname == "least_privilege":
                for k, eng in comp_eng.items():
                    import copy
                    rr = eng.discover(copy.deepcopy(spec), pol1)
                    from taas.manifest import manifest_tokens
                    res[f"Full-{k}"] = (rr.toolkit or [], rr.toolkit is None,
                                        manifest_tokens(rr.manifest["tools"]) if rr.manifest else 0,
                                        bool(rr.certificate and rr.certificate.valid),
                                        rr.counterexample.kind if rr.counterexample else "")
            pool_e = sorted(elig1)
            sq = M.subqueries(spec)
            bl = {"rag_mcp@5": lambda p: w.rank(t["query"], p, ("den",))[:5],
                  "mcp_zero": lambda p: mz.select(t["id"], p, 1),
                  "colt@5": lambda p: colt.ranked(t["query"], p)[:5],
                  "toolscope@5": lambda p: sorted(ts.expand(ts.select(t["query"], sq, p, 5))),
                  "cmtf_path": lambda p: cm.plan(spec, p)["path"],
                  "per_subtask": lambda p: [x for q in sq for x in w.rank(q, p, ("lex", "den"))[:1]],
                  "all_tools": lambda p: list(p)}
            for name, f in bl.items():
                res[f"{name}|unfiltered"] = (f(w.pool), False, None, None, "")
                res[f"{name}|eligible"] = (f(pool_e), False, None, None, "")
            oos = out_of_scope(need)
            for name, (K, ab, mtok, valid, chi) in res.items():
                K = list(dict.fromkeys(K))
                ev = SE.evaluate(K, rec, need, verified=elig1)
                reach = {a: attack_success(K, B, a) for a in oos}
                sanitised = name.startswith(("Full_PaMCP", "PaMCP_NoGap", "PaMCP_Declared", "G0_P0_S1", "Full-"))
                pois = {}
                for dens in (0.1, 0.3):
                    hits = [float(bool(set(K) & rng_poison[(dens, sd)])) for sd in range(5)]
                    pois[f"poison_raw_{dens}"] = float(np.mean(hits))
                    mode = "alias" if sanitised else "raw"
                    scans = [canary_hits(visible_json(K, C_by_id, rng_poison[(dens, sd)], mode)) for sd in range(5)]
                    pois[f"poison_shown_{dens}"] = float(np.mean([any(x.values()) for x in scans]))
                    for f in CANARY:
                        pois[f"poison_shown_{f}_{dens}"] = float(np.mean([x[f] for x in scans]))
                    if sanitised:      # what the pre-Revision-2 sanitiser would have shown for the same toolkit
                        leg = [canary_hits(visible_json(K, C_by_id, rng_poison[(dens, sd)], "legacy")) for sd in range(5)]
                        pois[f"poison_shown_legacy_{dens}"] = float(np.mean([any(x.values()) for x in leg]))
                rows.append({"id": t["id"], "set": "LMB" if t["id"] in live_ids else "dev", "policy": pname,
                             "method": name, "abstain": ab, "size": len(K), "tokens": w.tokens(K),
                             "manifest_tokens": mtok if mtok is not None else w.tokens(K),
                             "recall": fe.group_recall(K, t["gold"]) if t["gold"] else float("nan"),
                             "joint": float(ev["joint"]), "E_ok": float(ev["E"]), "L_ok": float(ev["L"]),
                             "forbidden_tools": ev["forbidden_tools"], "n_oos": len(oos),
                             "reach": sum(reach.values()), "reach_any": float(any(reach.values())),
                             **{f"reach_{a}": float(v) for a, v in reach.items()},
                             "output_borne": float(output_borne(K, Bd)),
                             "exploitable_output": float(output_borne(K, Bd) and any(reach.values())), **pois,
                             "certified": valid, "chi": chi, "toolkit": K, "need": sorted(need)})
    for r in rows:
        r["abstain"] = float(r["abstain"])
        for dens in (0.1, 0.3):
            r.setdefault(f"poison_shown_legacy_{dens}", float("nan"))
    # Revision 2 (A1): the 60 development prompts selected K and w_rel, so the test split (95 LiveMCPBench
    # tasks) is reported separately; "all" keeps the paper's original aggregation.
    splits = {"all": rows, "test": [r for r in rows if r["set"] == "LMB"], "dev": [r for r in rows if r["set"] == "dev"]}
    agg = {k: aggregate(v) for k, v in splits.items()}
    summ, att, fac, per_method, n_tasks = agg["all"]
    by_split = {k: {"summary": v[0], "attack_rates": v[1], "factorial": v[2], "abstention_certification": v[3],
                    "n_tasks": v[4]} for k, v in agg.items() if k != "all"}
    cfg = {"tasks": n_tasks, "policies": ["least_privilege", "read_only"], "cells": {v: list(k) for k, v in
                                                                                     CELL_NAME.items()},
           "components": list(comps) + ["no_refinement"], "baselines": "unfiltered and eligible-only",
           "poison_density": [0.1, 0.3], "poison_seeds": 5, "same_tasks_registry_scoring": True}
    raw = fe.save_raw("E18_factorial", rows)
    fe.save("E18_factorial", {"summary": summ, "factorial": fac, "abstention_certification": per_method,
                              "by_split": {k: {x: v[x] for x in ("summary", "factorial", "abstention_certification",
                                                                 "n_tasks")} for k, v in by_split.items()}},
            "MEASURED (recall, size, tokens) and LABELLED (joint feasibility, effects under labels B); evidence "
            "SIMULATED from labels A; task success BLOCKED", config=cfg, raw=raw)
    fe.save("E14_injection", {"attack_rates": att, "summary": {k: v for k, v in summ.items()},
                              "by_split": {k: {"attack_rates": v["attack_rates"], "summary": v["summary"],
                                               "n_tasks": v["n_tasks"]} for k, v in by_split.items()}},
            "LABELLED (reachable actions under labels B), offline; executed actions BLOCKED", config=cfg, raw=raw)
    for m in ("Full_PaMCP", "PaMCP_NoGap", "PaMCP_Declared", "PaMCP_NoCert", "G0_P0_S0", "per_subtask|unfiltered",
              "per_subtask|eligible", "rag_mcp@5|unfiltered", "mcp_zero|unfiltered", "all_tools|unfiltered"):
        s = summ.get(f"least_privilege|{m}")
        a = att.get(f"least_privilege|{m}")
        if s:
            print(f"{m:26s} |K| {s['size']['mean']:.2f} tok {s['tokens']['mean']:.0f} rec {s['recall']['mean']:.3f} "
                  f"joint {s['joint']['mean']:.3f} reach {a['rate']:.3f} abst {s['abstain']['mean']:.2f}")
    for k in ("least_privilege|recall", "least_privilege|joint", "least_privilege|reach_any", "least_privilege|tokens"):
        print(k, "shapley", {x: round(y, 3) for x, y in fac[k]["shapley"].items()},
              "full-none", round(fac[k]["full_minus_none"], 3))


if __name__ == "__main__":
    main()
