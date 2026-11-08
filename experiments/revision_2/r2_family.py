"""Revision 2: the confirmatory family H1-H5 of docs/PREREGISTRATION_AMENDMENT_R2.md (Holm over H1-H5).

H1, H2 (request level, target-tool clusters): two-sided sign-flip on per-cluster sums of paired differences,
cluster bootstrap CI of the mean difference. H3-H5 (task level): fe.paired (sign-flip, bootstrap; H3 one-sided
non-inferiority with margin 0.05). H6 is not evaluated here (executed benchmark; see the amendment's condition).
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402


def load(name):
    with gzip.open(fe.RES / "raw" / f"{name}.jsonl.gz", "rt") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def cluster_test(a_rows, b_rows, key="hit1", seed=0, draws=20000):
    A = {r["id"]: r for r in a_rows}
    B = {r["id"]: r for r in b_rows}
    ids = sorted(set(A) & set(B))
    d = [A[i][key] - B[i][key] for i in ids]
    cl = [A[i]["target"] for i in ids]
    sums = defaultdict(float)
    for x, c in zip(d, cl):
        sums[c] += x
    s = np.array(list(sums.values()))
    rng = np.random.default_rng(seed)
    obs = abs(s.sum())
    signs = rng.choice([-1, 1], size=(draws, len(s)))
    p = float((np.abs((signs * s).sum(1)) >= obs - 1e-12).mean())
    return {"n": len(ids), "clusters": len(s), "mean_a": float(np.mean([A[i][key] for i in ids])),
            "mean_b": float(np.mean([B[i][key] for i in ids])), "diff": float(np.mean(d)),
            "ci": fe.boot_ci(d, clusters=cl), "p": p}


def main() -> None:
    x3 = [r for r in load("R2_X3_test") if r["pool"] == "B1m"]
    by = defaultdict(list)
    for r in x3:
        by[r["config"]].append(r)
    fam = {}
    fam["H1"] = {"test": "E8 Hit@1 (569 tools), PaMCP-v2 ranking vs tuned BM25 on the raw request",
                 **cluster_test(by["pamcp|A"], by["bm25|k1=1.5,b=0.9"])}
    fam["H2"] = {"test": "E8 Hit@1 (569 tools), PaMCP-v2 ranking vs PaMCP-v1 ranking (Eq. (5), prompt reach)",
                 **cluster_test(by["pamcp|A"], by["pamcp|E"])}
    v = load("R2_v2_eval")
    M = defaultdict(dict)
    for r in v:
        M[r["method"]][r["id"]] = r

    def vec(m, k, ids):
        return [float(M[m][i].get(k, float("nan"))) for i in ids]
    ids = sorted(set(M["pamcp_v2"]) & set(M["per_subtask"]))
    gold_ids = [i for i in ids if M["pamcp_v2"][i].get("has_gold")]
    t3 = fe.paired(vec("pamcp_v2", "recall", gold_ids), vec("per_subtask", "recall", gold_ids), margin=0.05)
    fam["H3"] = {"test": "E9 group recall, PaMCP-v2 vs per-subtask (non-inferiority, margin 0.05)", **t3,
                 "p_two_sided": t3["p"], "p": t3["p_noninferior"]}
    fam["H4"] = {"test": "E10 joint feasibility (strict evaluator), PaMCP-v2 vs per-subtask restricted to eligible",
                 **fe.paired(vec("pamcp_v2", "joint_strict", ids), vec("per_subtask", "joint_strict", ids))}
    fam["H5"] = {"test": "E14 scope-aware definite out-of-scope reachability, PaMCP-v2 vs per-subtask unfiltered",
                 **fe.paired(vec("pamcp_v2", "scope_definite", ids), vec("per_subtask", "scope_definite", ids))}
    holm = fe.holm({k: fam[k]["p"] for k in fam})
    for k in fam:
        fam[k]["p_holm"] = holm[k]
        fam[k]["significant_0.05"] = holm[k] < 0.05
    # exploratory context (not in the family): v2 vs v1 on the same task-level outcomes
    ctx = {}
    for k in ("recall", "joint_paper", "joint_strict", "scope_definite", "scope_possible"):
        ii = gold_ids if k == "recall" else ids
        ctx[f"pamcp_v2 vs pamcp_v1 | {k}"] = fe.paired(vec("pamcp_v2", k, ii), vec("pamcp_v1", k, ii))
    fe.save("R2_family", {"family": fam, "exploratory_context": ctx,
                          "amendment": "docs/PREREGISTRATION_AMENDMENT_R2.md"},
            "Confirmatory tests of the R2 amendment (H1-H5); H6 conditional on the executed benchmark")
    for k, x in fam.items():
        print(k, f"diff {x['diff']:+.3f} ci {[round(c, 3) for c in x['ci']]} p {x['p']:.4f} p_holm {x['p_holm']:.4f}",
              x["test"])


if __name__ == "__main__":
    main()
