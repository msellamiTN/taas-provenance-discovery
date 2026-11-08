"""Revision 2, E21 / X8: experience reuse with mandatory revalidation.

Stream: the 300 MCPToolBench++ sample requests in a fixed shuffled order (seed 0), least-privilege policy per task.
Arms: cold (the recorded analyst specification for every request) and reuse (DiscoveryEngine.discover_prompt with a
PatternRepository: a stored pattern with Jaccard similarity >= 0.6 seeds the goal specification; certified toolkits
of cold requests are stored). Measured: pattern hit rate, analyst calls saved, Hit@1 and group recall of the
toolkit against gold, certification, latency.
Revalidation probes: for every request served from a pattern, the same request is discovered again after one change,
and we check that the revalidated toolkit respects the changed state:
  registry   the servers of the pattern's original toolkit are removed     -> no removed tool may appear
  revoked    the original toolkit's tools lose their verified evidence     -> none of them may be eligible/used
  hash       the original toolkit's tools change definition (rug pull)     -> stale evidence must not be used
  principal  strict read-only policy instead of least privilege            -> no non-read-only effect
  model      Claude Haiku's measured profile instead of Sonnet's           -> gap analysis re-run (toolkit may change)
Evidence: MEASURED (engine, recall vs gold); LABELLED (effects under J_B for the principal probe).
"""
from __future__ import annotations

import copy
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402
import methods as M  # noqa: E402
from taas.engine import DiscoveryEngine, EngineConfig  # noqa: E402
from taas.manifest import PatternRepository  # noqa: E402
from taas.policy import Policy  # noqa: E402


def make_engine(cs, profile="sonnet"):
    return DiscoveryEngine(cs, fe.profile(profile, strict=False), cfg=EngineConfig(), pair_policy=M.open_policy())


def main() -> None:
    cs = fe.contracts_cached("verified")
    C = {c.tool: c for c in cs}
    D = {c.tool: c for c in fe.contracts_cached("declared")}
    B = fe.labels_B()
    tasks = list(fe.tasks_e8_sample())
    random.Random(0).shuffle(tasks)
    eng = make_engine(cs)
    repo = PatternRepository()
    rows = []
    for t in tasks:
        spec, rec = fe.spec_for(t)
        if spec is None:
            continue
        pol, need = M.least_privilege(rec)
        t0 = time.perf_counter()
        cold = eng.discover(copy.deepcopy(spec), pol)
        t_cold = time.perf_counter() - t0
        t0 = time.perf_counter()
        r, reused = eng.discover_prompt(t["query"], lambda rec=rec: copy.deepcopy(rec), pol, repo)
        t_reuse = time.perf_counter() - t0
        row = {"id": t["id"], "reused": reused,
               "cold_hit1": fe.hit_at(cold.toolkit or [], t["gold"], 1) if cold.toolkit else 0.0,
               "cold_recall": fe.group_recall(cold.toolkit or [], t["gold"]),
               "reuse_recall": fe.group_recall(r.toolkit or [], t["gold"]),
               "cold_certified": bool(cold.certificate and cold.certificate.valid),
               "reuse_certified": bool(r.certificate and r.certificate.valid),
               "cold_ms": 1000 * t_cold, "reuse_ms": 1000 * t_reuse,
               "cold_toolkit": cold.toolkit or [], "reuse_toolkit": r.toolkit or []}
        if reused and r.toolkit:
            orig = list(r.toolkit)
            probes = {}
            # registry change: remove the servers of the toolkit
            gone = {C[x].server for x in orig}
            e2 = make_engine([c for c in cs if c.server not in gone])
            r2, _ = e2.discover_prompt(t["query"], lambda rec=rec: copy.deepcopy(rec), pol, repo, store=False)
            probes["registry"] = {"violations": len([x for x in (r2.toolkit or []) if C[x].server in gone]),
                                  "abstained": r2.toolkit is None}
            # revoked evidence / changed definition hash: the toolkit's tools keep only their published metadata
            # (declared contracts), as after a revocation or a rug pull that invalidates the hash-bound evidence
            e3 = make_engine([D[c.tool] if c.tool in orig else c for c in cs])
            r3, _ = e3.discover_prompt(t["query"], lambda rec=rec: copy.deepcopy(rec), pol, repo, store=False)
            probes["revoked_or_hash"] = {"violations": len([x for x in (r3.toolkit or []) if x in orig]),
                                         "abstained": r3.toolkit is None}
            # principal: strict read-only policy
            ro = Policy.make("ro", required={"read_only"}, lmin="obs")
            r4, _ = eng.discover_prompt(t["query"], lambda rec=rec: copy.deepcopy(rec), ro, repo, store=False)
            probes["principal"] = {"violations": len([x for x in (r4.toolkit or []) if B[x].unsafe_read_only]),
                                   "abstained": r4.toolkit is None}
            # model change
            e5 = make_engine(cs, "haiku")
            r5, _ = e5.discover_prompt(t["query"], lambda rec=rec: copy.deepcopy(rec), pol, repo, store=False)
            probes["model"] = {"changed": sorted(r5.toolkit or []) != sorted(orig), "abstained": r5.toolkit is None}
            row["probes"] = probes
        rows.append(row)
    reused = [r for r in rows if r["reused"]]
    pr = [r["probes"] for r in reused if "probes" in r]
    res = {"requests": len(rows), "reuse_hits": len(reused), "hit_rate": len(reused) / len(rows),
           "analyst_calls_saved": len(reused), "patterns_stored": len(repo.patterns),
           "recall_cold_on_reused": float(np.mean([r["cold_recall"] for r in reused])) if reused else None,
           "recall_reuse_on_reused": float(np.mean([r["reuse_recall"] for r in reused])) if reused else None,
           "same_toolkit_as_cold": float(np.mean([sorted(r["cold_toolkit"]) == sorted(r["reuse_toolkit"])
                                                  for r in reused])) if reused else None,
           "certified_cold": float(np.mean([r["cold_certified"] for r in rows])),
           "certified_reuse": float(np.mean([r["reuse_certified"] for r in rows])),
           "latency_ms_cold_p50": float(np.median([r["cold_ms"] for r in rows])),
           "latency_ms_reuse_p50": float(np.median([r["reuse_ms"] for r in rows]))}
    for k in ("registry", "revoked_or_hash", "principal"):
        res[f"probe_{k}_violations"] = int(sum(p[k]["violations"] for p in pr))
        res[f"probe_{k}_abstained"] = int(sum(p[k]["abstained"] for p in pr))
    res["probe_model_changed"] = int(sum(p["model"]["changed"] for p in pr))
    res["probes"] = len(pr)
    fe.save("R2_E21_reuse", {"results": res},
            "MEASURED (engine; recall vs gold); LABELLED (principal probe under J_B). The analyst saving is the LLM "
            "call avoided; patterns never bypass eligibility, evidence or the certificate.",
            config={"stream": "E8 300-query sample, shuffled with seed 0", "threshold": repo.threshold},
            raw=fe.save_raw("R2_E21_reuse", rows))
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items()})


if __name__ == "__main__":
    main()
