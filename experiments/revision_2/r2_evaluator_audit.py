"""Revision 2, review Major 7: audit of the E10 set evaluator.

1. Ten hand-built cases (the reviewer's list), each with a ground-truth verdict written before running either
   evaluator, scored with the paper's evaluator (``evaluate``) and the strict variant (``evaluate_strict``).
2. E10 re-scored with the strict variant on the toolkits saved in results/final/raw/E10_validity.jsonl.gz.
Evidence class: hand-built ground truth for (1); LABELLED (J_B) for (2).
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402
import methods as M  # noqa: E402
import set_evaluator as SE  # noqa: E402


def T(out, ins=None, classes=("read",), private=False):
    return {"out": out, "in": dict(ins or {}), "classes": list(classes), "private": private}


def G(gid, out, eff=(), sigma="data"):
    return {"id": gid, "out": out, "eff": list(eff), "sigma": sigma}


# (name, tools, goals, prompt inputs, task need classes, required args per tool or None, truth: joint feasible?,
#  checks the truth depends on, whether the labels carry the information needed)
CASES = [
    ("same shape, different meaning", {"t1": T("record:review[]", {"q": "query"})},
     [G("g", "record:invoice[]")], ["text"], set(), None, False, "S", True),
    ("same basic type, incompatible domain", {"t1": T("text:translation", {"x": "text"})},
     [G("g", "text:summary")], ["text"], set(), None, False, "S", True),
    ("required identifier not obtainable", {"t1": T("record:order", {"customer_id": "identifier:customer"})},
     [G("g", "record:order")], ["text"], set(), {"t1": {"customer_id"}}, False, "C", True),
    ("array versus scalar", {"t1": T("record:review", {"q": "query"})},
     [G("g", "record:review[]")], ["text"], set(), None, False, "S", True),
    ("resource scope mismatch (write outside /reports)",
     {"t1": T("document:report", {"x": "text"}, classes=("write",))},
     [G("g", "document:report", eff=("write(/reports)",))], ["text"], {"write"}, None, False, "E (scope)", False),
    ("prerequisite or credential missing", {"t1": T("record:issue", {"q": "query"})},
     [G("g", "record:issue")], ["text"], set(), None, False, "C (credentials)", False),
    ("private data and indirect egress (fixed destination)",
     {"t1": T("record:customer[]", {"q": "query"}, private=True),
      "t2": T("none", {"msg": "text"}, classes=("egress",))},
     [G("g1", "record:customer[]"), G("g2", "none", eff=())], ["text"], set(), None, False, "L", True),
    ("declassification with an unmet condition",
     {"t1": T("record:salary[]", {"q": "query"}, private=True),
      "t2": T("table:stats", {"x": "record"}),
      "t3": T("none", {"msg": "text"}, classes=("egress_any",))},
     [G("g1", "table:stats")], ["text"], {"egress_any"}, None, False, "L (declassification)", False),
    ("optional argument of an unobtainable kind",
     {"t1": T("record:weather", {"city": "text", "station_url": "url:station"})},
     [G("g", "record:weather")], ["text"], set(), {"t1": {"city"}}, True, "C", True),
    ("pairwise-safe tools, multi-tool violation (private -> file -> publisher)",
     {"t1": T("record:patient[]", {"q": "query"}, private=True),
      "t2": T("document:file", {"x": "text"}, classes=("write",)),
      "t3": T("none", {"f": "document:file"}, classes=("egress",))},
     [G("g1", "record:patient[]"), G("g2", "document:file", eff=("write(/tmp)",))], ["text"], {"write"}, None,
     False, "L", True),
]


def audit_cases() -> list[dict]:
    out = []
    orig = fe.labels_B_raw
    for name, tools, goals, prompt, need, req, truth, check, informative in CASES:
        rec = {"goals": goals, "prompt_inputs": prompt}
        fe.labels_B_raw = lambda tools=tools: tools
        try:
            a = SE.evaluate(list(tools), rec, set(need))
        finally:
            fe.labels_B_raw = orig
        b = SE.evaluate_strict(list(tools), rec, set(need), required=req, labels=tools)
        out.append({"case": name, "truth_joint": truth, "check": check, "labels_carry_the_information": informative,
                    "paper_evaluator_joint": a["joint"], "strict_evaluator_joint": b["joint"],
                    "paper_correct": a["joint"] == truth, "strict_correct": b["joint"] == truth})
    return out


def rescore_e10() -> dict:
    with gzip.open(fe.REFERENCE / "raw" / "E10_validity.jsonl.gz", "rt") as fh:
        rows = [json.loads(x) for x in fh if x.strip()]
    tasks = {t["id"]: t for t in fe.tasks_live()}
    req = {t.id: set((t.input_schema or {}).get("required") or []) for t in fe.raw()}
    w = M.World()
    cache = {}
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        t = tasks.get(r["id"])
        if t is None:
            continue
        if r["id"] not in cache:
            spec, rec = fe.spec_for(t)
            pol, need = M.least_privilege(rec)
            cache[r["id"]] = (rec, need, set(w.eligible(1, pol)))
        rec, need, elig = cache[r["id"]]
        K = r.get("toolkit") or []
        s = SE.evaluate_strict(K, rec, need, verified=elig, required=req)
        for c in ("S", "C", "E", "L", "M", "joint"):
            agg[r["method"]][c + "_strict"].append(float(bool(s[c])))
        agg[r["method"]]["joint_paper"].append(float(bool(r["joint"])))
    return {m: {k: sum(v) / len(v) for k, v in d.items()} | {"n": len(d["joint_paper"])} for m, d in agg.items()}


def main() -> None:
    cases = audit_cases()
    e10 = rescore_e10()
    acc = {v: sum(c[f"{v}_correct"] for c in cases) for v in ("paper", "strict")}
    fe.save("R2_evaluator_audit", {"cases": cases, "correct": acc, "n_cases": len(cases), "e10_strict": e10},
            "Hand-built ground truth (cases); LABELLED (E10 re-scoring under J_B)",
            notes="Truth verdicts were written before either evaluator was run on the cases. Cases whose deciding "
                  "information (resource scope, credentials, declassification conditions) is absent from the "
                  "labels cannot be decided by either evaluator.")
    for c in cases:
        print(f"{c['case'][:60]:60s} truth={c['truth_joint']!s:5} paper={c['paper_evaluator_joint']!s:5} "
              f"strict={c['strict_evaluator_joint']!s:5}")
    print("correct", acc)
    for m in ("pamcp(K=10)", "per_subtask[analyst]|eligible-only", "toolscope[analyst]@5|eligible-only",
              "rag_mcp@5|eligible-only", "pamcp_nocert"):
        if m in e10:
            print(m, {k: round(v, 3) for k, v in e10[m].items()})


if __name__ == "__main__":
    main()
