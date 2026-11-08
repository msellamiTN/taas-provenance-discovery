"""Revision 2, X7: construction of the risk relation, heterogeneous registries, real subsamples, concurrency.

1. Equality: PaMCP toolkits on the 94 LiveMCPBench tasks with eager, partitioned and lazy risk relations.
2. Build time of the engine (eager / partitioned / lazy) on cloned registries (E15's generator) and on
   heterogeneous generated registries.
3. Heterogeneous registries: servers, tools per server, effect mix, private share (forbidden-pair density),
   evidence sparsity, type-vocabulary size (shared intermediate types), duplicate rate; per-stage latency
   p50/p95 on generated goal specifications, abstention rate, peak memory.
4. Real-registry subsamples (100, 200, 400, 569 tools) with the 30 tasks of E15.
5. Concurrency: throughput with 1 and 2 worker processes (fork) on the real registry.
Evidence class: MEASURED latencies on 2 vCPUs; SYNTHETIC registries for 2-3.
"""
from __future__ import annotations

import copy
import multiprocessing as mp
import random
import resource
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402
import methods as M  # noqa: E402
import e15_e16_scale_evolution as E15  # noqa: E402
from taas.composer import ComposerConfig, eligible_set  # noqa: E402
from taas.contracts import QoS, make_contract  # noqa: E402
from taas.engine import DiscoveryEngine, EngineConfig  # noqa: E402
from taas.policy import Policy  # noqa: E402

MODES = ("eager", "partitioned", "lazy")
QUICK = "--quick" in sys.argv


def pctl(xs, q):
    return float(np.percentile(xs, q)) if xs else float("nan")


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def engine(cs, mode, policy=None):
    t0 = time.perf_counter()
    eng = DiscoveryEngine(cs, fe.profile("sonnet"), cfg=EngineConfig(pair_mode=mode),
                          pair_policy=policy or M.open_policy())
    return eng, time.perf_counter() - t0


# ------------------------------------------------------------------------------------------------ 1 equality
def equality() -> dict:
    cs = fe.contracts_cached("verified")
    tasks = [t for t in fe.tasks_live() if t["gold"]]
    out = {}
    tk = {}
    for mode in MODES:
        eng, bt = engine(cs, mode)
        ks = []
        for t in tasks:
            spec, rec = fe.spec_for(t)
            if spec is None:
                continue
            pol, _ = M.least_privilege(rec)
            r = eng.discover(copy.deepcopy(spec), pol)
            ks.append((t["id"], tuple(sorted(r.toolkit)) if r.toolkit is not None else None,
                       bool(r.certificate and r.certificate.valid)))
        tk[mode] = ks
        out[f"build_s|{mode}"] = bt
    out["tasks"] = len(tk["eager"])
    out["identical_partitioned"] = tk["partitioned"] == tk["eager"]
    out["identical_lazy"] = tk["lazy"] == tk["eager"]
    return out


# ------------------------------------------------------------------------------------------------ 2-3 generators
DOMAINS = ["order", "customer", "invoice", "review", "ticket", "file", "page", "event", "metric", "message",
           "product", "account", "report", "image", "repo", "issue", "post", "song", "flight", "weather"]
KINDS = ["record", "table", "document", "text", "url", "identifier"]


def hetero(n: int, servers: int, effect_mix: dict, private_share: float, sparse: float, vocab: int, dup: float,
           seed: int = 0):
    """Generated registry: tool i of server s consumes 0-2 typed inputs and produces one typed output drawn from a
    vocabulary of `vocab` domain types; effects drawn from `effect_mix`; evidence level lex with probability
    `sparse`, else ann/obs/att; a share `dup` of tools are near-duplicates of an earlier tool."""
    rng = random.Random(seed)
    types = [f"{rng.choice(KINDS)}:{DOMAINS[i % len(DOMAINS)]}{i // len(DOMAINS) or ''}" for i in range(vocab)]
    effs, weights = zip(*effect_mix.items())
    out = []
    for i in range(n):
        s = f"srv{i % servers}"
        if out and rng.random() < dup:
            b = rng.choice(out)
            c = make_contract(f"{s}::dup{i}", {a.name: str(a.type) for a in b.args}, str(b.head),
                              [str(e) for e in b.eff], rng.choice(["lex", "ann", "obs", "att"]),
                              tool_class=b.tool_class, description=b.description + " (mirror)",
                              source_label=b.flow.source_label, qos=QoS(rng.random(), rng.random(), 0.01))
        else:
            out_t = rng.choice(types)
            ins = {f"a{j}": rng.choice(types + ["query", "text"]) for j in range(rng.choice([0, 1, 1, 2]))}
            eff = rng.choices(effs, weights)[0]
            lvl = "lex" if rng.random() < sparse else rng.choice(["ann", "obs", "obs", "att"])
            c = make_contract(f"{s}::tool{i}", ins or {"q": "query"}, out_t, eff, lvl,
                              tool_class=rng.choice(["retrieve", "convert_format", "aggregate", "write", "search"]),
                              description=f"produce {out_t.replace(':', ' ')} from {' '.join(ins.values()) or 'query'}",
                              source_label="private" if rng.random() < private_share else "public",
                              qos=QoS(rng.random(), rng.random(), 0.01))
        out.append(c)
    return out, types


def goal_specs(types, k: int, seed: int = 1):
    rng = random.Random(seed)
    specs = []
    for i in range(k):
        n = rng.choice([1, 2, 3])
        gs = [{"id": f"g{j}", "desc": f"obtain {t.replace(':', ' ')}", "class": "retrieve", "in": ["query"],
               "out": t, "eff": [], "sigma": "data", "n": 1} for j, t in enumerate(rng.sample(types, n))]
        specs.append({"id": f"s{i}", "prompt_inputs": ["query", "text"], "goals": gs})
    return specs


def request_latency(eng, specs, policy):
    from taas.goals import parse_goal_spec
    st = {"eligibility": [], "total": []}
    ab = 0
    for sp in specs:
        spec = parse_goal_spec(copy.deepcopy(sp))
        t0 = time.perf_counter()
        eligible_set(eng.index, policy)
        st["eligibility"].append(time.perf_counter() - t0)
        r = eng.discover(spec, policy)
        st["total"].append(r.time_s)
        ab += r.toolkit is None
    return {"eligibility_p50_ms": 1000 * pctl(st["eligibility"], 50), "total_p50_ms": 1000 * pctl(st["total"], 50),
            "total_p95_ms": 1000 * pctl(st["total"], 95), "abstain_share": ab / len(specs)}


HETERO = {   # name -> generator parameters (defaults, then one factor varied at a time)
    "default": dict(servers=200, effect_mix={("read(db)",): 6, ("read(web)", "egress(*)"): 2, ("write(fs)",): 1,
                                             ("delete(fs)",): 0.3, ("exec",): 0.2, ("egress(slack)",): 0.5},
                    private_share=0.15, sparse=0.5, vocab=60, dup=0.1),
    "few_servers": dict(servers=20),
    "effect_heavy": dict(effect_mix={("read(db)",): 2, ("read(web)", "egress(*)"): 3, ("write(fs)",): 3,
                                     ("delete(fs)",): 1, ("exec",): 1, ("egress(slack)",): 1}),
    "dense_forbidden": dict(private_share=0.5),
    "no_annotations": dict(sparse=0.95),
    "small_vocabulary": dict(vocab=15),
    "many_duplicates": dict(dup=0.4),
}


def hetero_runs() -> dict:
    out = {}
    pol = Policy.make("p", required=(), allowed=("read(*)", "egress(*)", "write(fs)"), lmin=0.0)
    sizes = (1000, 10000) if QUICK else (1000, 10000, 100000)
    for name, over in HETERO.items():
        params = {**HETERO["default"], **over}
        for n in sizes if name == "default" else sizes[:2]:
            cs, types = hetero(n, params["servers"], {tuple(k): v for k, v in params["effect_mix"].items()},
                               params["private_share"], params["sparse"], params["vocab"], params["dup"])
            cs = [c for c in cs]
            specs = goal_specs(types, 20)
            row = {}
            # beyond 10k tools a materialised relation (eager or partitioned) needs O(n^2) memory (3.07M pairs at
            # 10k in the default mix; the 100k partitioned run was killed at 7 GB): only the lazy relation is run there
            for mode in (MODES if n <= 10000 else ("lazy",)):
                eng, bt = engine(cs, mode, pol)
                row[f"build_s|{mode}"] = bt
                row[f"pairs|{mode}"] = len(eng.H.forbidden) if mode != "lazy" else None
                if mode == "lazy":
                    row |= request_latency(eng, specs, pol)
                del eng
            row["peak_rss_mb"] = rss_mb()
            out[f"{name}|{n}"] = row
            print("hetero", name, n, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()})
    return out


def cloned_builds() -> dict:
    out = {}
    for n in ((569, 1000, 10000) if QUICK else (569, 1000, 10000, 100000)):
        raw, orig = E15.clones(n)
        J = {t.id: fe.labels_A()[orig[t.id]] for t in raw}
        store = fe.verifier_store(J, raw_tools=raw)
        from taas.contracts import extract_contract
        from taas.realreg import typing_for
        cs = [extract_contract(t, typing_for(orig[t.id]), store) for t in raw]
        row = {}
        for mode in (MODES if n <= 10000 else ("partitioned", "lazy")):
            eng, bt = engine(cs, mode)
            row[f"build_s|{mode}"] = bt
            del eng
        out[str(n)] = row
        print("clones", n, {k: round(v, 2) for k, v in row.items()})
    return out


# ------------------------------------------------------------------------------------------------ 4 subsamples
def subsamples() -> dict:
    cs_all = fe.contracts_cached("verified")
    tasks = [t for t in fe.tasks_live() if t["gold"]][:30]
    out = {}
    for n in (100, 200, 400, 569):
        rng = random.Random(n)
        cs = cs_all if n == 569 else rng.sample(cs_all, n)
        eng, bt = engine(cs, "lazy")
        tot, ab = [], 0
        for t in tasks:
            spec, rec = fe.spec_for(t)
            pol, _ = M.least_privilege(rec)
            r = eng.discover(copy.deepcopy(spec), pol)
            tot.append(r.time_s)
            ab += r.toolkit is None
        out[str(n)] = {"build_s": bt, "total_p50_ms": 1000 * pctl(tot, 50), "total_p95_ms": 1000 * pctl(tot, 95),
                       "abstain_share": ab / len(tasks)}
        print("subsample", n, {k: round(v, 3) for k, v in out[str(n)].items()})
    return out


# ------------------------------------------------------------------------------------------------ 5 concurrency
_ENG = None
_SPECS = None


def _init():
    global _ENG, _SPECS
    _ENG, _ = engine(fe.contracts_cached("verified"), "lazy")


def _work(i):
    t = _SPECS[i]
    spec, rec = fe.spec_for(t)
    pol, _ = M.least_privilege(rec)
    _ENG.discover(copy.deepcopy(spec), pol)
    return i


def concurrency() -> dict:
    global _SPECS
    _SPECS = [t for t in fe.tasks_live() if t["gold"] and fe.spec_for(t)[0] is not None]
    out = {}
    for workers in (1, 2):
        with mp.get_context("fork").Pool(workers, initializer=_init) as pool:
            pool.map(_work, range(min(4, len(_SPECS))))          # warm-up
            t0 = time.perf_counter()
            pool.map(_work, range(len(_SPECS)))
            dt = time.perf_counter() - t0
        out[str(workers)] = {"requests": len(_SPECS), "seconds": dt, "requests_per_s": len(_SPECS) / dt}
        print("concurrency", workers, {k: round(v, 3) for k, v in out[str(workers)].items()})
    return out


def main() -> None:
    part = fe.RES / "R2_X7_partial.json"
    res = json.loads(part.read_text()) if part.exists() else {}
    for key, fn in (("equality", equality), ("subsamples", subsamples), ("concurrency", concurrency),
                    ("cloned_builds", cloned_builds), ("heterogeneous", hetero_runs)):
        if key not in res:
            res[key] = fn()
            part.write_text(json.dumps(res))
        print(key, "done")
    fe.save("R2_X7_scale", {"results": res},
            "MEASURED (latency, memory on 2 vCPUs); SYNTHETIC (clones, heterogeneous generator)",
            config={"modes": MODES, "hetero": {k: {kk: (str(vv) if kk == "effect_mix" else vv) for kk, vv in v.items()}
                                               for k, v in HETERO.items()}, "quick": QUICK})


if __name__ == "__main__":
    main()
