"""Revision 2, model-profile calibration (review Major 11): scoring, profiles, threshold selection, held-out risk.

Inputs: data/llm_inputs/r2_calibration/{items.json, gold.json}; data/llm_records/r2_calibration/
answers_<model>_batch_<k>.json (answers produced by reading only, no tools) and self_assessment_<model>.json
(per-cell probability of an exactly correct answer, given before any item was seen).
Outputs (results/revision_2/R2_X2_calibration.json):
* accuracy per model, overall and by class, n, language, noise and embedding (Wilson 95% intervals);
* self-assessment calibration: Brier score, ECE (10 equal-width bins) and the reliability table, item level;
* measured profile: ModelProfile.from_calibration on the calibration split (isotonic in n, per class, both languages);
* threshold tau chosen on the calibration split as the smallest tau whose selective risk (error among items declared
  native) is at most the risk target (0.05, 0.10), then evaluated on the held-out test split: coverage (share of
  items declared native), selective risk, and missed-native share (items not declared native that the model answered
  correctly). Three profiles are compared at the same targets: measured (this suite), self-assessed (the model's own
  per-cell estimate) and the 64-item profile used in the manuscript (data/processed/profile_<model>.json, tau 0.9);
* with and without the manuscript's exactness rule (exact classes beyond n = 20 are never native).
Missing answers count as wrong. Noisy join items: the generator's gold compares ids case-insensitively, which the
question text does not state; accuracy is also reported accepting either reading (sensitivity). Evidence: MEASURED (gold computed by the generator; answers by the models).
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402
from taas.model_profile import ModelProfile  # noqa: E402

IN = ROOT / "data" / "llm_inputs" / "r2_calibration"
REC = ROOT / "data" / "llm_records" / "r2_calibration"
MODELS = ("haiku", "sonnet", "opus")
TARGETS = (0.05, 0.10)
EXACT_ITEM_CLASSES = {"count", "compute_exactly"}


def _num(s: str) -> float | None:
    s = s.replace(" ", " ").replace(" ", " ")
    s = re.sub(r"(?<=\d)[ ,](?=\d{3}\b)", "", s)          # thousands separators
    m = re.search(r"-?\d+(?:[.,]\d+)?", s)
    return float(m.group(0).replace(",", ".")) if m else None


def join_case_sensitive(item: dict) -> int:
    A = item["data"][0][3:].split(", ")
    B = item["data"][1][3:].split(", ")
    return len(set(A) & set(B))


def correct(item: dict, gold, ans, lenient_join: bool = False) -> bool:
    if lenient_join and item["class"] == "join" and item["noisy"]:
        return correct(item, gold, ans) or correct(item, join_case_sensitive(item), ans)
    if ans is None:
        return False
    a = str(ans).strip()
    k = item["kind"]
    if k == "int":
        x = _num(a)
        return x is not None and abs(x - float(gold)) < 1e-9
    if k == "approx":
        x = _num(a)
        return x is not None and abs(x - float(gold)) <= 0.05 * abs(float(gold))
    if k == "set":
        got = set(re.findall(r"K\d{7}", a))
        return got == set(gold)
    if k == "idvalue":
        gid, gv = str(gold).split(",", 1)
        m = re.search(r"(R\d{6})\D+?(\d+(?:\.\d+)?)", a)
        return bool(m) and m.group(1) == gid and abs(float(m.group(2)) - float(gv)) < 0.005
    raise ValueError(k)


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def cell(it: dict) -> str:
    return f"{it['class']}|{it['n']}|{it['lang']}|{int(it['noisy'])}|{int(it['embedded'])}"


def exactness(it: dict) -> str:
    if it["class"] in EXACT_ITEM_CLASSES or it.get("exactness") == "exact":
        return "exact"
    return "tolerant"


def load_answers(model: str) -> dict:
    out = {}
    for f in sorted(REC.glob(f"answers_{model}_batch_*.json")):
        j = json.loads(f.read_text())
        a = j.get("answers", j) if isinstance(j, dict) else j
        if isinstance(a, dict):
            out.update(a)
    return out


def load_self(model: str) -> dict:
    f = REC / f"self_assessment_{model}.json"
    if not f.exists():
        return {}
    j = json.loads(f.read_text())
    return {k: float(v) for k, v in j.get("answers", j).items()} if isinstance(j, dict) else {}


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10):
    edges = np.linspace(0, 1, bins + 1)
    tab, e = [], 0.0
    for i in range(bins):
        m = (p >= edges[i]) & ((p < edges[i + 1]) if i < bins - 1 else (p <= edges[i + 1]))
        if m.any():
            tab.append({"bin": [float(edges[i]), float(edges[i + 1])], "n": int(m.sum()),
                        "mean_conf": float(p[m].mean()), "accuracy": float(y[m].mean())})
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e), tab


def selective(conf: np.ndarray, y: np.ndarray, tau: float) -> dict:
    nat = conf >= tau
    n = len(y)
    return {"coverage": float(nat.mean()) if n else float("nan"),
            "selective_risk": float(1 - y[nat].mean()) if nat.any() else 0.0,
            "native_items": int(nat.sum()),
            "missed_native": float(((~nat) & (y == 1)).sum() / n) if n else float("nan")}


def choose_tau(conf: np.ndarray, y: np.ndarray, target: float) -> float:
    """Smallest threshold with selective risk <= target on these items (1.0+ means: declare nothing native)."""
    for t in sorted(set(np.round(conf, 6))):
        nat = conf >= t
        if nat.any() and 1 - y[nat].mean() <= target:
            return float(t)
    return 1.000001


def conf_measured(prof: ModelProfile, it: dict, exact_rule: bool) -> float:
    if exact_rule:
        return prof.rho(it["class"], it["n"], it["lang"], exactness(it))
    m = prof._measured(it["class"], it["n"], it["lang"])
    return 0.0 if m is None else m


def main() -> None:
    items = json.loads((IN / "items.json").read_text())
    gold = json.loads((IN / "gold.json").read_text())
    res, raw_rows = {}, []
    for model in MODELS:
        ans = load_answers(model)
        sa = load_self(model)
        if not ans:
            continue
        rows = []
        for it in items:
            a = ans.get(it["id"])
            y = int(correct(it, gold[it["id"]], a))
            y_len = int(correct(it, gold[it["id"]], a, lenient_join=True))
            rows.append({"correct_either_join_reading": y_len, "model": model, "id": it["id"], "split": it["split"], "class": it["class"], "n": it["n"],
                         "lang": it["lang"], "noisy": it["noisy"], "embedded": it["embedded"],
                         "exactness": exactness(it), "answered": a is not None, "correct": y,
                         "self_p": sa.get(cell(it), float("nan"))})
        raw_rows += rows
        Y = np.array([r["correct"] for r in rows])
        r_m = {"answered": int(sum(r["answered"] for r in rows)), "items": len(rows),
               "accuracy": float(Y.mean()), "accuracy_ci": wilson(int(Y.sum()), len(Y)),
               "accuracy_either_join_reading": float(np.mean([r["correct_either_join_reading"] for r in rows])),
               "noisy_join_items": int(sum(1 for r in rows if r["class"] == "join" and r["noisy"])),
               "noisy_join_correct_case_insensitive": int(sum(r["correct"] for r in rows
                                                              if r["class"] == "join" and r["noisy"])),
               "noisy_join_correct_either": int(sum(r["correct_either_join_reading"] for r in rows
                                                    if r["class"] == "join" and r["noisy"]))}
        for dim in ("class", "n", "lang", "noisy", "embedded", "exactness"):
            g = defaultdict(list)
            for r in rows:
                g[str(r[dim])].append(r["correct"])
            r_m[f"by_{dim}"] = {k: {"n": len(v), "accuracy": float(np.mean(v)), "ci": wilson(sum(v), len(v))}
                                for k, v in sorted(g.items())}
        cn = defaultdict(list)
        for r in rows:
            cn[f"{r['class']}|{r['n']}"].append(r["correct"])
        r_m["by_class_n"] = {k: float(np.mean(v)) for k, v in sorted(cn.items())}
        # ---- self-assessment calibration (item level)
        if sa:
            P = np.array([r["self_p"] for r in rows])
            ok = ~np.isnan(P)
            e, tab = ece(P[ok], Y[ok])
            r_m["self_assessment"] = {"cells": len(sa), "items_with_estimate": int(ok.sum()),
                                      "mean_conf": float(P[ok].mean()), "brier": float(np.mean((P[ok] - Y[ok]) ** 2)),
                                      "ece": e, "overconfidence": float(P[ok].mean() - Y[ok].mean()),
                                      "reliability": tab}
        # ---- profiles and held-out selective risk
        cal = [r for r, it in zip(rows, items) if it["split"] == "calibration"]
        tst_idx = [i for i, it in enumerate(items) if it["split"] == "test"]
        cal_idx = [i for i, it in enumerate(items) if it["split"] == "calibration"]
        prof = ModelProfile.from_calibration(f"claude-{model}-r2", [{"class": r["class"], "n": r["n"],
                                                                    "correct": r["correct"]} for r in cal])
        for cp in prof.classes.values():
            cp.langs = ("en", "fr")
        (ROOT / "data" / "processed").mkdir(exist_ok=True)
        old = None
        old_f = ROOT / "data" / "processed" / f"profile_{model}.json"
        if old_f.exists():
            old = ModelProfile.load(old_f)
            old.strict = True
            for cp in old.classes.values():
                cp.langs = tuple(cp.langs)
        sel = {}
        for exact_rule in (True, False):
            for name in ("measured", "self_assessed") + (("manuscript_64",) if old else ()):
                if name == "self_assessed" and not sa:
                    continue
                if name == "measured":
                    conf = np.array([conf_measured(prof, it, exact_rule) for it in items])
                elif name == "self_assessed":
                    conf = np.array([sa.get(cell(it), 0.0) for it in items])
                    if exact_rule:
                        conf = np.array([min(c, prof.tau - 1e-6) if exactness(it) == "exact" and it["n"] > prof.exact_n_max
                                         else c for c, it in zip(conf, items)])
                else:
                    conf = np.array([conf_measured(old, it, exact_rule) for it in items])
                key = f"{name}|exact_rule={exact_rule}"
                sel[key] = {}
                cc, yc = conf[cal_idx], Y[cal_idx]
                ct, yt = conf[tst_idx], Y[tst_idx]
                for tgt in TARGETS:
                    tau = choose_tau(cc, yc, tgt)
                    sel[key][f"target={tgt}"] = {"tau": tau, "calibration": selective(cc, yc, tau),
                                                 "test": selective(ct, yt, tau)}
                sel[key]["manuscript_tau=0.9"] = {"tau": 0.9, "calibration": selective(cc, yc, 0.9),
                                                  "test": selective(ct, yt, 0.9)}
        r_m["selection"] = sel
        r_m["profile_r2"] = prof.to_json()
        (ROOT / "data" / "processed" / f"profile_{model}_r2.json").write_text(json.dumps(prof.to_json(), indent=1))
        res[model] = r_m
    notes = REC / "agent_notes.json"
    fe.save("R2_X2_calibration", {"results": res,
                                  "agent_notes": json.loads(notes.read_text()) if notes.exists() else {}},
            "MEASURED: 432 generated items with exact gold (six classes, n in {10, 40, 160, 640}, en/fr, clean/noisy, "
            "isolated/embedded), answered by reading only; calibration/test split fixed by the generator. "
            "Self-assessment given before any item was seen.",
            config={"targets": TARGETS, "ece_bins": 10, "missing_answer": "wrong",
                    "exact_classes": sorted(EXACT_ITEM_CLASSES) + ["aggregate_sum (exact items)"]},
            raw=fe.save_raw("R2_X2_calibration", raw_rows))
    for m, r in res.items():
        s = r.get("self_assessment", {})
        print(m, f"acc {r['accuracy']:.3f} answered {r['answered']}/{r['items']}",
              f"self conf {s.get('mean_conf', float('nan')):.3f} ECE {s.get('ece', float('nan')):.3f} "
              f"Brier {s.get('brier', float('nan')):.3f}")
        print("   by class", {k: round(v["accuracy"], 2) for k, v in r["by_class"].items()})
        print("   by n", {k: round(v["accuracy"], 2) for k, v in r["by_n"].items()})
        for k, v in r["selection"].items():
            if k.endswith("True"):
                print("  ", k, {t: (round(x["tau"], 3), round(x["test"]["coverage"], 3),
                                    round(x["test"]["selective_risk"], 3)) for t, x in v.items()})


if __name__ == "__main__":
    main()
