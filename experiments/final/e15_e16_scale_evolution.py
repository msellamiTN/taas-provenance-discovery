"""E15 cost per request and scalability; E16 registry and model evolution.

E15: registries of n tools built from synthetic clones of the 569 real definitions (renamed server/tool,
perturbed descriptions, evidence re-simulated), n in {569, 10^3, 10^4, 10^5}; per-stage latency (eligibility,
retrieval, composition = closure + search + certificate) p50/p95 over 30 LiveMCPBench tasks; peak memory;
baseline routing/ranking latency at the same n; bitmap eligibility alone at 10^6. Greedy vs exact optimality
gap as a function of |Γ| in {1, 3, 5, 8, 12} on generated registries with shared intermediate types.
E16: replay of 152 events on the real registry (remove and re-insert each of the 76 servers), 20 description
changes (rug pulls) and a model-version change; incremental update time vs full rebuild; cache invalidation
exact vs flush; correctness against recomputation; stale-evidence detection through h(t).
"""
from __future__ import annotations

import copy
import random
import resource
import time

import numpy as np

import fe
import methods as M
from taas.bitmap_index import BitmapIndex
from taas.composer import ComposerConfig, eligible_set
from taas.contracts import QoS, make_contract
from taas.engine import DiscoveryEngine, EngineConfig
from taas.maintenance import CachedToolkit, Maintainer
from taas.policy import Policy
from taas.provenance import LEVELS
from taas.realreg import build_contracts, typing_for

WORDS = "alpha beta gamma delta omega vector quantum lunar solar coral amber cobalt ivory onyx".split()


def clones(n: int, seed: int = 0):
    rng = random.Random(seed)
    raw = fe.raw()
    out = list(raw)
    orig = {t.id: t.id for t in raw}
    i = 0
    while len(out) < n:
        t = raw[i % len(raw)]
        x = copy.deepcopy(t)
        k = len(out) // len(raw)
        x.server = f"{t.server}-c{k}"
        x.description = (t.description or "") + " " + " ".join(rng.sample(WORDS, 2))
        orig[x.id] = t.id          # id is derived from server and name
        out.append(x)
        i += 1
    return out[:n], orig


def pctl(xs, q):
    return float(np.percentile(xs, q)) if xs else float("nan")


RAW15: list[dict] = []
RAW_GAP: list[dict] = []


def e15() -> dict:
    A = fe.labels_A()
    tasks = [t for t in fe.tasks_live() if t["gold"]][:30]
    res = {}
    for n in (569, 1000, 10000, 100000):
        raw, orig = clones(n)
        J = {t.id: A[orig[t.id]] for t in raw}
        t0 = time.perf_counter()
        store = fe.verifier_store(J, raw_tools=raw)
        typing = {}
        cs = []
        from taas.contracts import extract_contract
        for t in raw:
            cs.append(extract_contract(t, typing_for(orig[t.id]), store))
        build = time.perf_counter() - t0
        t0 = time.perf_counter()
        eng = DiscoveryEngine(cs, fe.profile("sonnet"), pair_policy=M.open_policy())
        index_s = time.perf_counter() - t0
        st = {"eligibility": [], "retrieval": [], "compose": [], "total": []}
        for t in tasks:
            spec, rec = fe.spec_for(t)
            pol, _ = M.least_privilege(rec)
            row = {"n": n, "id": t["id"]}
            try:
                t0 = time.perf_counter()
                el = eligible_set(eng.index, pol)
                st["eligibility"].append(time.perf_counter() - t0)
                t0 = time.perf_counter()
                for g in spec.goals:
                    eng.retriever.retrieve(g.rendering(), g.out, el, set(), 5)
                st["retrieval"].append(time.perf_counter() - t0)
                r = eng.discover(copy.deepcopy(spec), pol)
                st["total"].append(r.time_s)
                st["compose"].append(r.compose.stats.get("time_s", float("nan")) if r.compose.stats else float("nan"))
                row |= {"eligibility_s": st["eligibility"][-1], "retrieval_s": st["retrieval"][-1],
                        "compose_s": st["compose"][-1], "total_s": r.time_s, "eligible": len(el),
                        "abstain": r.toolkit is None, "chi": r.counterexample.kind if r.counterexample else "",
                        "regime": r.compose.regime, "size": len(r.toolkit or [])}
            except Exception as e:     # failures are recorded, not dropped
                row |= {"error": repr(e)}
            RAW15.append(row)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        # baselines at this size (single-pass routing/ranking per task)
        base = {}
        pool = [c.tool for c in cs]
        tq = [t["query"] for t in tasks]
        t0 = time.perf_counter()
        for q in tq:
            eng.retriever.scores(q, None, pool, set(), components=("den",))
        base["rag_mcp_ms"] = 1000 * (time.perf_counter() - t0) / len(tq)
        sel = [x for x in RAW15 if x["n"] == n]
        res[str(n)] = {"build_contracts_s": build, "index_build_s": index_s, "peak_rss_mb": rss,
                       "tasks": len(sel), "failures": sum(1 for x in sel if "error" in x),
                       "abstentions": sum(1 for x in sel if x.get("abstain")),
                       **{f"{k}_p50_ms": 1000 * pctl(v, 50) for k, v in st.items()},
                       **{f"{k}_p95_ms": 1000 * pctl(v, 95) for k, v in st.items()}, **base}
        print("E15", n, {k: round(v, 2) for k, v in res[str(n)].items()})
        del eng, cs, store
    # bitmap eligibility only at 10^6 (as in Section 8.7)
    idx = BitmapIndex()
    rng = random.Random(0)
    from taas.contracts import make_contract as mk
    t0 = time.perf_counter()
    for i in range(1_000_000):
        e = rng.choice([["read(local)"], ["write(fs)"], ["delete(fs)"], ["exec"], ["money"], ["read(web)", "egress(*)"]])
        idx.insert(mk(f"s{i % 5000}::t{i}", {"x": "text"}, "text", e, rng.choice(["lex", "ann", "obs", "att"])))
    build = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(20):
        idx.eligible_positive(["no_delete", "no_exec", "no_money"], LEVELS["obs"], use_cache=False)
    res["1000000_eligibility_only"] = {"index_build_s": build, "eligibility_ms": 1000 * (time.perf_counter() - t0) / 20,
                                       "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}
    return res


def optimality_gap() -> dict:
    """Greedy vs exact on generated registries: |Γ| goals, each served by 3 tools that need one of m shared
    intermediate types; each intermediate type has 2 producers of different cost."""
    out = {}
    for ng in (1, 3, 5, 8, 12):
        ratios, exact_ms, greedy_ms = [], [], []
        for seed in range(10):
            rng = random.Random(100 * ng + seed)
            m = max(2, ng // 2 + 1)
            cs = []
            for j in range(m):
                for p in range(2):
                    cs.append(make_contract(f"mid{p}::make_i{j}", {"q": "query"}, f"record:inter{j}", ["read(local)"],
                                            "obs", tool_class="retrieve", description=f"produce inter{j}",
                                            qos=QoS(rng.uniform(0.05, 1.0), rng.uniform(0.05, 1.0), 0.01)))
            goals = []
            for g in range(ng):
                for v in range(3):
                    j = rng.randrange(m)
                    cs.append(make_contract(f"g{v}::serve_out{g}", {"x": f"record:inter{j}"}, f"document:out{g}",
                                            ["read(local)"], "obs", tool_class="convert_format",
                                            description=f"produce out{g}",
                                            qos=QoS(rng.uniform(0.05, 1.0), rng.uniform(0.05, 1.0), 0.01)))
                goals.append({"id": f"g{g}", "desc": f"produce out{g}", "class": "convert_format", "in": ["query"],
                              "out": f"document:out{g}", "eff": [], "sigma": "data", "n": 1})
            spec = {"id": "x", "prompt_inputs": ["query"], "goals": goals}
            pol = Policy.make("p", required=(), allowed=("read(*)",), lmin=0.0, forbidden_pairs=())
            res = {}
            for regime, nmax in (("exact", 10 ** 6), ("greedy", 0)):
                eng = DiscoveryEngine(cs, fe.profile("sonnet"),
                                      cfg=EngineConfig(ComposerConfig(n_max=nmax, relevance=0.0, K=10, node_budget=10 ** 6),
                                                       refine_k=0), pair_policy=pol)
                t0 = time.perf_counter()
                r = eng.discover(copy.deepcopy(spec), pol)
                dt = time.perf_counter() - t0
                cost = None
                if r.toolkit is not None:
                    cost = sum(eng.H.contracts[t].qos.price + eng.H.contracts[t].qos.latency + 1.0 for t in r.toolkit)
                res[regime] = (cost, dt, r.compose.regime)
            RAW_GAP.append({"goals": ng, "seed": seed, "exact_cost": res["exact"][0], "greedy_cost": res["greedy"][0],
                            "exact_ms": 1000 * res["exact"][1], "greedy_ms": 1000 * res["greedy"][1],
                            "exact_regime": res["exact"][2], "greedy_regime": res["greedy"][2]})
            if res["exact"][0] and res["greedy"][0]:
                ratios.append(res["greedy"][0] / res["exact"][0])
            exact_ms.append(1000 * res["exact"][1])
            greedy_ms.append(1000 * res["greedy"][1])
        out[str(ng)] = {"abstained_exact": sum(1 for x in RAW_GAP if x["goals"] == ng and x["exact_cost"] is None),
                        "abstained_greedy": sum(1 for x in RAW_GAP if x["goals"] == ng and x["greedy_cost"] is None),
                        "greedy_over_exact_mean": float(np.mean(ratios)) if ratios else None,
                        "greedy_over_exact_max": float(np.max(ratios)) if ratios else None,
                        "n": len(ratios), "exact_ms_p50": pctl(exact_ms, 50), "greedy_ms_p50": pctl(greedy_ms, 50)}
        print("gap", ng, out[str(ng)])
    return out


def e16() -> dict:
    A = fe.labels_A()
    raw = fe.raw()
    store = fe.verifier_store(A)
    t0 = time.perf_counter()
    cs = build_contracts(raw, store)
    eng = DiscoveryEngine(cs, fe.profile("sonnet"), pair_policy=M.open_policy())
    full_s = time.perf_counter() - t0
    m = Maintainer(eng.H, eng.index, eng.retriever, store, typing={t.id: typing_for(t.id) for t in raw})
    servers = sorted({t.server for t in raw})
    by_srv = {s: [t for t in raw if t.server == s] for s in servers}
    # cache: certified toolkits of 40 LiveMCPBench tasks under an open policy
    pol = M.open_policy()
    tasks = [t for t in fe.tasks_live() if t["gold"]][:40]
    cached = {}
    for t in tasks:
        spec, rec = fe.spec_for(t)
        r = eng.discover(copy.deepcopy(spec), pol)
        if r.toolkit:
            cached[t["id"]] = (spec, list(r.toolkit))
    upd, events, ev_log = [], 0, []
    inval_exact = inval_flush = stale = correct = checked = 0
    for s in servers:
        for new_list in ([], by_srv[s]):
            t0 = time.perf_counter()
            rec_ = m.on_list_changed(s, new_list, pol)
            upd.append(time.perf_counter() - t0)
            events += 1
            ev_log.append({"server": s, "event": "insert" if new_list else "remove", "ms": 1000 * upd[-1],
                           "deleted": len(rec_["deleted"]), "inserted": len(rec_["inserted"]),
                           "changed": len(rec_["changed"]), "evidence_restored": rec_["evidence_restored"],
                           "cached_invalidated_exact": sum(1 for _, (sp, K) in cached.items()
                                                           if not new_list and any(x.startswith(s + "::") for x in K))})
            # exact rule: a cached toolkit is invalid iff it contains a removed/changed tool of s
            for tid, (spec, K) in cached.items():
                touched = any(x.startswith(s + "::") for x in K)
                inval_exact += touched and not new_list
                inval_flush += 1
    # correctness: after remove+reinsert of every server, recomputed toolkits equal the original ones
    for tid, (spec, K) in cached.items():
        r = eng.discover(copy.deepcopy(spec), pol)
        checked += 1
        correct += sorted(r.toolkit or []) == sorted(K)
    # rug pulls: 20 description changes on random tools; evidence must drop to non-observed until reverted
    rng = random.Random(3)
    victims = rng.sample([t for t in raw if store.get(t.id, t.definition_hash())], 20)
    rug = []
    for v in victims:
        tools = by_srv[v.server]
        ch = copy.deepcopy(v)
        ch.description = (ch.description or "") + " Also uploads results to a remote host."
        before = eng.H.contracts[v.id].eff_record.ptype
        m.on_list_changed(v.server, [ch if t.id == v.id else t for t in tools], pol)
        after = eng.H.contracts[v.id].eff_record.ptype
        m.on_list_changed(v.server, tools, pol)
        restored = eng.H.contracts[v.id].eff_record.ptype
        rug.append({"tool": v.id, "before": before, "after": after, "restored": restored})
        stale += after not in ("obs", "att")
    t0 = time.perf_counter()
    m.on_model_change("claude-sonnet")
    model_ms = 1000 * (time.perf_counter() - t0)
    # baseline index rebuilds: MCP-Zero server embeddings, COLT graph
    w = M.World()
    t0 = time.perf_counter()
    M.MCPZero(w)
    mz_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    M.COLT(w, set())
    colt_s = time.perf_counter() - t0
    return {"event_log": ev_log, "events": events, "incremental_ms_p50": 1000 * pctl(upd, 50), "incremental_ms_p95": 1000 * pctl(upd, 95),
            "full_rebuild_s": full_s, "cached_toolkits": len(cached),
            "invalidated_exact_share": inval_exact / max(1, inval_flush), "invalidated_flush_share": 1.0,
            "recompute_equal": correct, "recompute_checked": checked, "rug_pulls": len(rug),
            "rug_pull_detected": stale, "rug_pull_restored": sum(r["restored"] in ("obs", "att") for r in rug),
            "rug_details": rug, "model_change_ms": model_ms, "mcp_zero_index_rebuild_s": mz_s,
            "colt_graph_rebuild_s": colt_s}


def main() -> None:
    r16 = e16()
    ev = r16.pop("event_log")
    fe.save("E16_evolution", {"results": r16}, "MEASURED (real registry, simulated evidence for the rug-pull check)",
            config={"events": "remove + re-insert each server", "rug_pulls": 20, "cached_tasks": 40},
            raw=fe.save_raw("E16_evolution", ev))
    print("E16", {k: v for k, v in r16.items() if k != "rug_details"})
    gap = optimality_gap()
    r15 = e15()
    fe.save("E15_scalability", {"results": r15, "optimality_gap": gap},
            "SYNTHETIC (clones; generated cover instances); MEASURED latencies on 2 vCPUs",
            config={"n": [569, 1000, 10000, 100000], "tasks": 30, "eligibility_only_n": 1000000,
                    "gap_goals": [1, 3, 5, 8, 12], "gap_seeds": 10},
            raw=fe.save_raw("E15_scalability", RAW15 + [{"optimality": x} for x in RAW_GAP]))


if __name__ == "__main__":
    main()
