"""E12 model-profile calibration (Sonnet, Haiku, Opus; self-assessment control; refutation of the analyst's
native claims by the engine) and E11 capability gap and bridge ratio on review-type tasks.

E12 uses the existing 64-item calibration set (4 classes x n in {10, 40, 160, 640} x 4 items). The protocol's
10-class, 30k, three-script corpus is not built here (reported as a scope limit).
E11 varies the executing model's measured profile, the threshold tau and the input size n of a review-type
goal specification (the analyst's own record for the running review scenario, with n and exactness changed).
Task success needs execution (E13) and is not measured.
"""
from __future__ import annotations

import copy
import json
import re

import fe
from taas.engine import DiscoveryEngine, EngineConfig
from taas.composer import ComposerConfig
from taas.goals import gap_analysis, parse_goal_spec
from taas.model_profile import DEFAULT_PRIORS, ModelProfile

import methods as M


def correct(ans, gold) -> bool:
    a = str(ans).strip().lower()
    g = gold["answer"]
    if isinstance(g, int):
        m = re.search(r"-?\d[\d,]*", a)
        return bool(m) and int(m.group(0).replace(",", "")) == g
    return str(g).lower() in a


RAW12: list[dict] = []


def e12() -> tuple[dict, dict]:
    gold = json.load(open(fe.ROOT / "data/calibration/gold.json"))
    index = {d["id"]: d for d in json.load(open(fe.ROOT / "data/calibration/index.json"))}
    out, recs_by = {}, {}
    for model in ("sonnet", "haiku", "opus"):
        ans = json.load(open(fe.REC / f"calibration_answers_{model}.json"))
        self_a = json.load(open(fe.REC / f"calibration_self_assessment_{model}.json"))["self_assessment"]
        recs = [{"class": it["class"], "n": it["n"], "correct": correct(ans.get(i, ""), gold[i])}
                for i, it in index.items()]
        RAW12.extend({"model": model, "item": i, "class": it["class"], "n": it["n"], "answer": ans.get(i),
                      "gold": gold[i]["answer"], "correct": correct(ans.get(i, ""), gold[i])} for i, it in index.items())
        recs_by[model] = recs
        cells = {}
        for r in recs:
            cells.setdefault(r["class"], {}).setdefault(r["n"], []).append(r["correct"])
        meas = {c: {str(n): {"acc": sum(v) / len(v), "k": sum(v), "n": len(v), "ci": fe.wilson(sum(v), len(v))}
                    for n, v in sorted(d.items())} for c, d in cells.items()}
        err = [abs(self_a[c][n] - meas[c][n]["acc"]) for c in meas for n in meas[c]]
        brier = [(self_a[c][n] - r["correct"]) ** 2 for r in recs for c, n in [(r["class"], str(r["n"]))]]
        over = sum(self_a[c][n] - meas[c][n]["acc"] for c in meas for n in meas[c]) / len(err)
        out[model] = {"measured": meas, "self_assessed": self_a, "overall_accuracy": sum(r["correct"] for r in recs) / 64,
                      "self_assessment_mae": sum(err) / len(err), "self_assessment_brier": sum(brier) / len(brier),
                      "mean_signed_error": over}
    # refutation: goals the analyst declared native that the engine (Sonnet profile) moves into the gap
    prof = fe.profile("sonnet")
    claimed_native = refuted = 0
    for t in fe.tasks_live() + fe.tasks_dev():
        spec, rec = fe.spec_for(t)
        if spec is None:
            continue
        gr = gap_analysis(copy.deepcopy(spec), prof, "all_predecessors")
        gap_ids = {g.id for g in gr.gap}
        for g in rec["goals"]:
            if g.get("sigma") == "native" and not g.get("optional"):
                claimed_native += 1
                refuted += g["id"] in gap_ids
    out["refutation"] = {"claimed_native": claimed_native, "refuted_by_engine": refuted,
                         "rate": refuted / claimed_native if claimed_native else float("nan")}
    return out, recs_by


def e11(recs_by: dict) -> dict:
    from taas.scenarios import reviews_policy, reviews_registry, reviews_spec
    base = reviews_spec()                       # running review scenario (Fig. 1); its registry, plus the
    cs = list(reviews_registry())    # the scenario's own registry (with the 569 public tools added, the K=5
    # shortlist of g5 fills with public document tools and the engine abstains with chi1; reported in notes)
    pol = reviews_policy()
    out = {}
    for model, recs in recs_by.items():
        for tau in (0.6, 0.75, 0.9):
            prof = ModelProfile.from_calibration(f"claude-{model}", recs, tau=tau, priors=DEFAULT_PRIORS)
            prof.strict = False
            engines = {g: DiscoveryEngine(cs, prof, cfg=EngineConfig(ComposerConfig(), use_gap=g),
                                          pair_policy=pol) for g in (True, False)}
            for n in (30, 300, 3000, 30000):
                for exact in ("tolerant", "exact"):
                    rec = copy.deepcopy(base)
                    for g in rec["goals"]:
                        if int(g.get("n", 1)) > 1:
                            g["n"] = n
                        if g["class"] in ("aggregate", "classify"):
                            g["exactness"] = exact
                    for use_gap, eng in engines.items():
                        spec = parse_goal_spec(copy.deepcopy(rec), "review scenario")
                        r = eng.discover(spec, pol)
                        G = [g for g in spec.goals if not g.optional]
                        out[f"{model}|{tau}|{n}|{exact}|{'gap' if use_gap else 'nogap'}"] = {
                            "size": len(r.toolkit or []), "abstain": r.toolkit is None, "gap": len(r.gap.gap),
                            "goals": len(G), "native_share": 1 - len(r.gap.gap) / len(G),
                            "beta": r.certificate.bridge_ratio if r.certificate else None,
                            "chi": r.counterexample.kind if r.counterexample else "", "toolkit": r.toolkit}
    return out


def main() -> None:
    r12, recs = e12()
    fe.save("E12_profile", {"results": r12}, "MEASURED (model answers vs gold); self-assessment recorded",
            inputs=["data/calibration/gold.json", "data/calibration/index.json"],
            notes="64-item set; protocol's 10-class/30k/three-script corpus not built (scope limit).",
            config={"models": ["sonnet", "haiku", "opus"], "tau": 0.9}, raw=fe.save_raw("E12_profile", RAW12))
    r11 = e11(recs)
    fe.save("E11_gap", {"results": r11}, "MEASURED (engine on a review-type goal spec); task success BLOCKED (E13)",
            config={"models": ["sonnet", "haiku", "opus"], "tau": [0.6, 0.75, 0.9], "n": [30, 300, 3000, 30000],
                    "exactness": ["tolerant", "exact"], "registry": "review scenario (Fig. 1)"})
    for m in ("sonnet", "haiku", "opus"):
        print(m, round(r12[m]["overall_accuracy"], 3), "MAE", round(r12[m]["self_assessment_mae"], 3),
              "signed", round(r12[m]["mean_signed_error"], 3))
    print("refutation", r12["refutation"])
    for k in ("sonnet|0.9|30|exact|gap", "sonnet|0.9|30000|exact|gap", "haiku|0.9|300|exact|gap",
              "haiku|0.9|300|exact|nogap", "opus|0.9|3000|tolerant|gap"):
        print(k, {x: r11[k][x] for x in ("size", "gap", "native_share", "beta")})


if __name__ == "__main__":
    main()
