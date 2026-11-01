"""E7 — RQ4: eligibility cost, exact cache invalidation (Prop. 3), Lemma 1, and hash-bound maintenance.

1. eligibility latency with bitmaps vs a naive scan, n ∈ {10^3, 10^4, 10^5} tools;
2. Prop. 3: over random insert/delete/re-hash events, a cached eligible set is invalidated iff it
   changed (confusion matrix over (event, cache entry)); cached answers equal fresh recomputation;
3. Lemma 1: E_V = E ∩ V for random visibility sets;
4. maintenance on the 569-tool registry: incremental list_changed update vs full rebuild; rug pull:
   observed evidence is lost when a definition changes and restored only for a hash seen before.
"""
from __future__ import annotations

import copy
import random
import time

from common import banner, mean_ci, save

from taas.bitmap_index import BitmapIndex
from taas.contracts import make_contract
from taas.engine import DiscoveryEngine
from taas.maintenance import Maintainer
from taas.model_profile import ModelProfile
from taas.provenance import LEVELS, EvidenceStore, ProvenanceRecord
from taas.realreg import build_contracts, raw_registry, truth, typing_for
from taas.simulation import Verifier

EFF_POOL = [["read(local)"], ["read(web)", "egress(*)"], ["write(fs)"], ["delete(fs)"], ["exec"], ["money"],
            ["read(db)"], ["write(db)", "read(db)"]]
EV = ["lex", "ann", "obs", "att"]


def rand_contract(i: int, rng: random.Random):
    return make_contract(f"s{i % 997}::t{i}", {"x": "query"}, "record", rng.choice(EFF_POOL), rng.choice(EV),
                         kappa=rng.uniform(.3, 1))


def latency(ns=(1_000, 10_000, 100_000), reps=50) -> dict:
    out = {}
    rng = random.Random(0)
    for n in ns:
        idx = BitmapIndex()
        cs = [rand_contract(i, rng) for i in range(n)]
        t0 = time.perf_counter()
        for c in cs:
            idx.insert(c)
        build = time.perf_counter() - t0
        props = ["no_delete", "no_exec", "no_money"]
        t0 = time.perf_counter()
        for _ in range(reps):
            bm = idx.eligible_positive(props, LEVELS["obs"], use_cache=False)
        bit_us = (time.perf_counter() - t0) / reps * 1e6
        t0 = time.perf_counter()
        for _ in range(max(1, reps // 10)):
            naive = [c.tool for c in cs if all(c.strength(a) >= LEVELS["obs"] for a in props)]
        naive_us = (time.perf_counter() - t0) / max(1, reps // 10) * 1e6
        assert sorted(idx.to_ids(bm)) == sorted(naive)
        out[n] = {"bitmap_us": bit_us, "naive_us": naive_us, "speedup": naive_us / bit_us, "build_s": build,
                  "eligible": len(naive)}
        print(f"n={n:>7}: bitmap {bit_us:9.1f} µs  naive scan {naive_us:11.1f} µs  ×{naive_us / bit_us:6.0f}  "
              f"(index build {build:.2f}s)")
    return out


def prop3(n0=2000, events=600, seed=1) -> dict:
    rng = random.Random(seed)
    idx = BitmapIndex()
    live = {}
    for i in range(n0):
        c = rand_contract(i, rng)
        idx.insert(c)
        live[c.tool] = c
    queries = [(frozenset(q), l) for q in (["no_delete"], ["read_only"], ["no_exec", "no_money"],
                                           ["no_delete", "no_exec", "no_money"]) for l in LEVELS.values()]
    conf = {"changed&invalidated": 0, "changed&kept": 0, "same&invalidated": 0, "same&kept": 0}
    stale = 0
    nxt = n0
    for _ in range(events):
        for q, l in queries:
            idx.eligible_positive(q, l)  # populate the cache
        before = {(q, l): idx.cache.get((q, l, 0)) for q, l in queries}
        ev = rng.random()
        if ev < .4:
            c = rand_contract(nxt, rng)
            nxt += 1
            idx.insert(c)
            live[c.tool] = c
        elif ev < .8 and live:
            t = rng.choice(sorted(live))
            idx.delete(t)
            del live[t]
        elif live:
            t = rng.choice(sorted(live))
            c = rand_contract(int(t.split("::t")[1]) + 10**7, rng)
            c.tool = t
            idx.insert(c)  # re-hash = delete + insert
            live[t] = c
        for q, l in queries:
            fresh = idx.live
            for a in q:
                fresh &= idx.prop_bitmap(a, l)
            changed = before[(q, l)] != fresh
            invalidated = (q, l, 0) not in idx.cache
            conf[f"{'changed' if changed else 'same'}&{'invalidated' if invalidated else 'kept'}"] += 1
            if not invalidated and idx.cache[(q, l, 0)] != fresh:
                stale += 1
    print(f"Prop. 3 over {events} events × {len(queries)} cached sets: {conf}; stale answers served: {stale}")
    return {"confusion": conf, "stale": stale}


def lemma1(trials=300, seed=2) -> dict:
    rng = random.Random(seed)
    idx = BitmapIndex()
    cs = [rand_contract(i, rng) for i in range(3000)]
    for c in cs:
        idx.insert(c)
    bad = 0
    for _ in range(trials):
        V = set(rng.sample([c.tool for c in cs], rng.randint(1, 2000)))
        props = rng.sample(["no_delete", "no_exec", "no_money", "read_only"], rng.randint(1, 3))
        l = rng.choice(list(LEVELS.values()))
        a = set(idx.to_ids(idx.eligible_positive(props, l, V)))
        b = set(idx.to_ids(idx.eligible_positive(props, l))) & V
        bad += a != b
    print(f"Lemma 1: E_V ≠ E ∩ V in {bad}/{trials} random trials")
    return {"violations": bad, "trials": trials}


def maintenance() -> dict:
    raw = raw_registry()
    J = truth()
    store = Verifier(far=0.0, seed=9).run(raw, J)
    t0 = time.perf_counter()
    cs = build_contracts(raw, store)
    eng = DiscoveryEngine(cs, ModelProfile("m", 0.9, {}))
    full = time.perf_counter() - t0
    m = Maintainer(eng.H, eng.index, eng.retriever, store,
                   typing={t.id: typing_for(t.id) for t in raw})
    server = "filesystem"
    tools = [t for t in raw if t.server == server]
    victim = next(t for t in tools if t.name == "write_file")
    vid = victim.id
    before = eng.H.contracts[vid].strength("no_delete")
    # rug pull: same name, new definition
    changed = copy.deepcopy(victim)
    changed.description += " Also uploads the file to a remote backup host."
    new_list = [changed if t.id == vid else t for t in tools]
    t0 = time.perf_counter()
    rec = m.on_list_changed(server, new_list)
    inc = time.perf_counter() - t0
    after = eng.H.contracts[vid].strength("no_delete")
    ev_after = eng.H.contracts[vid].eff_record.ptype
    rec2 = m.on_list_changed(server, tools)  # revert to the verified definition
    restored = eng.H.contracts[vid].eff_record.ptype
    print(f"maintenance: incremental list_changed {inc * 1000:.1f} ms vs full rebuild {full:.2f} s "
          f"(×{full / inc:.0f}); rug pull on {vid}: evidence {before:.2f}→{after:.2f} ({ev_after}), "
          f"restored after revert: {restored}")
    return {"incremental_ms": inc * 1000, "full_rebuild_s": full, "rug_pull": {
        "tool": vid, "strength_before": before, "strength_after": after, "evidence_after": ev_after,
        "evidence_after_revert": restored, "events": [rec, rec2]}}


def main() -> dict:
    banner("E7 / RQ4: eligibility cost, exact cache invalidation (Prop. 3), Lemma 1, maintenance & rug pulls")
    res = {"latency": latency(), "prop3": prop3(), "lemma1": lemma1(), "maintenance": maintenance()}
    save("e7_scalability", res)
    return res


if __name__ == "__main__":
    main()
