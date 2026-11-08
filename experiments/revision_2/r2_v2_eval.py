"""Revision 2: PaMCP-v2 (configuration fixed on dev, docs/PREREGISTRATION_AMENDMENT_R2.md) on the test tasks.

PaMCP-v2 toolkits are computed here; PaMCP-v1 and baseline toolkits come from the saved raw records of E9, E10 and
E18 (same tasks, registry, policies), so every method is scored by the same code below:
* E9-v2  (94 LiveMCPBench tasks with gold, open policy, K = 5): group recall, size, tokens, abstention;
* E10-v2 (least privilege, K = 10): joint feasibility under the paper's and the strict evaluator;
* E14-v2 (95 tasks, least privilege, K = 5): scope-aware reachability (Revision 1 estimand, regex fixed), canary
  exposure of the alias manifest.
Also writes the per-task vectors used by the confirmatory tests H3-H5 (experiments/revision_2/r2_family.py).
Evidence: MEASURED (recall vs gold); LABELLED (evaluators and reachability under J_B).
"""
from __future__ import annotations

import copy
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))
sys.path.insert(0, str(ROOT / "experiments" / "revision_1"))

import fe  # noqa: E402
import methods as M  # noqa: E402
import set_evaluator as SE  # noqa: E402
import e14_e18_factorial as E14  # noqa: E402
import reanalyse_e14_scope_aware as SA  # noqa: E402

V2 = dict(components=("lex",), uncertain_ok=True)


def raw(name):
    with gzip.open(fe.REFERENCE / "raw" / f"{name}.jsonl.gz", "rt") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def scope_row(K, rec, Bl):
    req = SA.task_requirements(rec, "least_privilege")
    att = {a: SA.evaluate_attack(K, a, req, Bl) for a in SA.ATTACK_CLASSES}
    d = any(x["reachable"] for x in att.values())
    i = any(x["indeterminate"] for x in att.values())
    return {"definite": float(d), "indeterminate": float(i), "possible": float(d or i)}


def main() -> None:
    tasks = [t for t in fe.tasks_live()]
    analysts = fe.analyst_records("sonnet")
    Bl = fe.labels_B()
    req_args = {t.id: set((t.input_schema or {}).get("required") or []) for t in fe.raw()}
    w5 = M.World(**V2)
    w10 = M.World(K=10, **V2)
    w1 = M.World()
    C = {c.tool: c for c in w5.cs["verified"]}
    pol_open = M.open_policy()
    rng_poison = {(0.3, sd): set(__import__("random").Random(1000 * sd + 30).sample(w5.pool, round(0.3 * len(w5.pool))))
                  for sd in range(5)}
    rows = []
    for t in tasks:
        spec, rec = fe.spec_for(t)
        if spec is None:
            continue
        pol, need = M.least_privilege(rec)
        elig = set(w5.eligible(1, pol))
        r9 = w5.pamcp(1, 1, 1, spec, rec, pol_open)
        r10 = w10.pamcp(1, 1, 1, spec, rec, pol)
        r14 = w5.pamcp(1, 1, 1, spec, rec, pol)
        K9, K10, K14 = list(r9["K"] or []), list(r10["K"] or []), list(r14["K"] or [])
        ev_p = SE.evaluate(K10, rec, need, verified=elig)
        ev_s = SE.evaluate_strict(K10, rec, need, verified=elig, required=req_args)
        sc = scope_row(K14, analysts.get(t["id"], rec), Bl)
        scans = [E14.canary_hits(E14.visible_json(K14, C, rng_poison[(0.3, sd)], "alias")) for sd in range(5)]
        rows.append({"id": t["id"], "method": "pamcp_v2", "has_gold": bool(t["gold"]),
                     "recall": fe.group_recall(K9, t["gold"]) if t["gold"] else float("nan"),
                     "size9": len(K9), "tokens9": w5.tokens(K9), "abstain9": float(bool(r9["abstain"])),
                     "joint_paper": float(ev_p["joint"]), "joint_strict": float(ev_s["joint"]),
                     "abstain10": float(bool(r10["abstain"])), "size14": len(K14),
                     "abstain14": float(bool(r14["abstain"])), **{f"scope_{k}": v for k, v in sc.items()},
                     "canary_shown_0.3": float(np.mean([any(x.values()) for x in scans])),
                     "K9": K9, "K10": K10, "K14": K14})
    # ------------------------------------------------------------------ comparators from saved records
    e9 = defaultdict(dict)
    for r in raw("E9_sets"):
        e9[r["method"]][r["id"]] = r
    e10 = defaultdict(dict)
    for r in raw("E10_validity"):
        e10[r["method"]][r["id"]] = r
    e18 = defaultdict(dict)
    for r in raw("E18_factorial"):
        if r["policy"] == "least_privilege" and r.get("set") == "LMB":
            e18[r["method"]][r["id"]] = r
    comp = {}
    for t in tasks:
        spec, rec = fe.spec_for(t)
        if spec is None:
            continue
        pol, need = M.least_privilege(rec)
        elig = set(w1.eligible(1, pol))
        for m9, m10, m18, lab in (("pamcp@5", "pamcp(K=10)", "Full_PaMCP", "pamcp_v1"),
                                   ("per_subtask[analyst]", "per_subtask[analyst]|eligible-only", "per_subtask|unfiltered",
                                    "per_subtask"),
                                   ("rag_mcp@5", "rag_mcp@5|eligible-only", "rag_mcp@5|unfiltered", "rag_mcp@5"),
                                   ("toolscope[analyst]@5", "toolscope[analyst]@5|eligible-only", "toolscope@5|unfiltered",
                                    "toolscope@5"),
                                   ("mcp_zero", "mcp_zero|eligible-only", "mcp_zero|unfiltered", "mcp_zero")):
            x9, x10, x18 = e9[m9].get(t["id"]), e10[m10].get(t["id"]), e18[m18].get(t["id"])
            row = {"id": t["id"], "method": lab}
            if x9:
                row |= {"recall": x9["recall"], "size9": x9["size"], "tokens9": x9["tokens"]}
            if x10:
                K = x10.get("toolkit") or []
                row |= {"joint_paper": float(bool(x10["joint"])),
                        "joint_strict": float(SE.evaluate_strict(K, rec, need, verified=elig,
                                                                 required=req_args)["joint"])}
            if x18:
                row |= {f"scope_{k}": v for k, v in scope_row(x18.get("toolkit") or [],
                                                              analysts.get(t["id"], rec), Bl).items()}
                row["canary_shown_0.3"] = x18.get("poison_shown_0.3", float("nan"))
            comp.setdefault(lab, []).append(row)
    allrows = rows + [r for v in comp.values() for r in v]
    summ = {}
    for m in sorted({r["method"] for r in allrows}):
        sel = [r for r in allrows if r["method"] == m]
        summ[m] = {k: float(np.nanmean([r[k] for r in sel if k in r])) for k in
                   ("recall", "size9", "tokens9", "abstain9", "joint_paper", "joint_strict", "scope_definite",
                    "scope_indeterminate", "scope_possible", "canary_shown_0.3")
                   if any(k in r for r in sel)}
        summ[m]["n"] = len(sel)
    fe.save("R2_v2_eval", {"summary": summ, "v2_config": {k: str(v) for k, v in V2.items()}},
            "MEASURED (recall vs gold); LABELLED (paper and strict evaluators, scope-aware reachability under J_B); "
            "canary scan of the model-visible manifest", raw=fe.save_raw("R2_v2_eval", allrows))
    for m, v in summ.items():
        print(f"{m:12s}", {k: round(x, 3) for k, x in v.items()})


if __name__ == "__main__":
    main()
