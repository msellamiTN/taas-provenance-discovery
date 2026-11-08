"""Scope-aware offline re-analysis of the saved E18 toolkits (Revision 1).

- Evaluates all five attack classes for every task; no tamper-class omission.
- Uses task-declared scopes and class-level JB scoring labels.
- Separates definite violations from indeterminate scope information.
- Aggregates attack outcomes within each task before paired inference.
- Marks the new F5-like comparison exploratory because its estimand differs from the original F5.

This remains an LLM-labelled static analysis, not a runtime attack experiment.
"""
from __future__ import annotations

import gzip
import json
import math
import os
from collections import defaultdict
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "src"))

import fe  # noqa: E402
from scope_policy import TaskEffectRequirements, classify_effect  # noqa: E402

ATTACK_CLASSES = {
    "destroy": frozenset({"delete"}),
    "execute": frozenset({"exec"}),
    "pay": frozenset({"money"}),
    "tamper": frozenset({"write", "delete", "exec", "money"}),
    "exfiltrate": frozenset({"egress"}),
}
METHOD_A = "Full_PaMCP"
METHOD_B = "per_subtask|unfiltered"


def load_gzip_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Required source result is missing: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def task_requirements(record: dict, policy: str) -> TaskEffectRequirements:
    if policy == "read_only":
        return TaskEffectRequirements((), frozenset(), ())
    required: list = []
    ambiguous: set[str] = set()
    raw_values: list[str] = []
    from taas.effects import parse_effect
    import re

    for goal in record.get("goals", []) or []:
        for item in goal.get("eff", []) or []:
            raw = str(item).strip().lower()
            if not raw:
                continue
            raw_values.append(raw)
            match = re.match(r"^\\s*([a-z]+)", raw)
            cls = match.group(1) if match else ""
            if cls in {"write", "delete", "egress"} and "(" not in raw:
                ambiguous.add(cls)
                continue
            try:
                required.append(parse_effect(raw))
            except ValueError:
                if cls:
                    ambiguous.add(cls)
    return TaskEffectRequirements(tuple(sorted(set(required))), frozenset(ambiguous), tuple(raw_values))


def evaluate_attack(toolkit: list[str], attack: str, requirements: TaskEffectRequirements,
                    labels_b: dict) -> dict:
    candidates = []
    private_source_present = any(labels_b.get(t) and labels_b[t].private_source for t in toolkit)
    for tool_id in toolkit:
        truth = labels_b.get(tool_id)
        if truth is None:
            continue
        for effect in truth.effects:
            if effect.cls in ATTACK_CLASSES[attack]:
                candidates.append((tool_id, effect))

    if attack == "exfiltrate" and not private_source_present:
        return {"reachable": False, "indeterminate": False, "reason": "no_private_source"}
    if not candidates:
        return {"reachable": False, "indeterminate": False, "reason": "no_candidate_effect"}

    statuses = [classify_effect(effect, requirements) for _, effect in candidates]
    definite = any(status == "violation" for status in statuses)
    indeterminate = (not definite) and any(status == "indeterminate" for status in statuses)
    return {
        "reachable": bool(definite),
        "indeterminate": bool(indeterminate),
        "reason": "out_of_scope_effect" if definite else "scope_unknown" if indeterminate else "all_effects_permitted",
        "candidate_effects": [f"{tool}:{effect}" for (tool, effect) in candidates],
        "statuses": statuses,
    }


def signflip_task(differences: np.ndarray, *, seed: int = 19, draws: int = 100_000) -> float:
    d = differences[np.isfinite(differences)]
    d = d[d != 0]
    if len(d) == 0:
        return 1.0
    observed = float(np.mean(d))
    if len(d) <= 16:
        signs = np.array(np.meshgrid(*[[-1.0, 1.0]] * len(d))).reshape(len(d), -1).T
    else:
        rng = np.random.default_rng(seed)
        signs = rng.choice([-1.0, 1.0], size=(draws, len(d)))
    null = np.mean(signs * np.abs(d), axis=1)
    return float((np.count_nonzero(np.abs(null) >= abs(observed) - 1e-12) + 1) / (len(null) + 1))


def cluster_bootstrap_ci(differences: np.ndarray, *, seed: int = 23, draws: int = 20_000) -> list[float]:
    d = differences[np.isfinite(differences)]
    if len(d) == 0:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(d), size=(draws, len(d)))
    means = d[indices].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def main() -> None:
    source = ROOT / "results" / "final" / "raw" / "E18_factorial.jsonl.gz"
    rows = load_gzip_jsonl(source)
    labels_b = fe.labels_B()
    analysts = fe.analyst_records("sonnet")
    tasks_by_method: dict[tuple[str, str], dict] = {}
    out_rows = []

    for row in rows:
        task_id = row["id"]
        method = row["method"]
        policy = row["policy"]
        record = analysts.get(task_id)
        if record is None:
            out_rows.append({"id": task_id, "method": method, "policy": policy, "status": "missing_goal_record"})
            continue
        requirements = task_requirements(record, policy)
        toolkit = row.get("toolkit") or []
        attacks = {
            attack: evaluate_attack(toolkit, attack, requirements, labels_b)
            for attack in ATTACK_CLASSES
        }
        definite_any = any(x["reachable"] for x in attacks.values())
        indeterminate_any = any(x["indeterminate"] for x in attacks.values())
        possible_any = definite_any or indeterminate_any
        out_rows.append({
            "id": task_id,
            "method": method,
            "policy": policy,
            "n_tools": len(toolkit),
            "n_explicit_required_effects": len(requirements.required),
            "ambiguous_required_classes": sorted(requirements.ambiguous_classes),
            "definite_oos_any": definite_any,
            "indeterminate_oos_any": indeterminate_any,
            "possible_oos_any": possible_any,
            "attacks": attacks,
        })
        tasks_by_method[(policy, method)] = tasks_by_method.get((policy, method), {})
        tasks_by_method[(policy, method)][task_id] = out_rows[-1]

    summary = {}
    for key, task_rows in tasks_by_method.items():
        outcomes = list(task_rows.values())
        n = len(outcomes)
        summary[f"{key[0]}|{key[1]}"] = {
            "n_tasks": n,
            "definite_oos_task_rate": sum(r["definite_oos_any"] for r in outcomes) / n if n else None,
            "indeterminate_task_rate": sum(r["indeterminate_oos_any"] for r in outcomes) / n if n else None,
            "conservative_possible_oos_task_rate": sum(r["possible_oos_any"] for r in outcomes) / n if n else None,
        }

    paired = {}
    left = tasks_by_method.get(("least_privilege", METHOD_A), {})
    right = tasks_by_method.get(("least_privilege", METHOD_B), {})
    ids = sorted(set(left) & set(right))
    if ids:
        # One paired observation per task. Unknown cases count as possible exposure in
        # this conservative upper-bound outcome; definite and indeterminate rates remain
        # separately reported above.
        d = np.array([
            float(left[i]["possible_oos_any"]) - float(right[i]["possible_oos_any"])
            for i in ids
        ])
        paired = {
            "contrast": f"{METHOD_A} minus {METHOD_B}",
            "unit": "task (attacks nested within task)",
            "n_tasks": len(ids),
            "mean_difference": float(np.mean(d)),
            "ci95_task_cluster_bootstrap": cluster_bootstrap_ci(d),
            "two_sided_signflip_p": signflip_task(d),
            "status": "EXPLORATORY_NOT_CONFIRMATORY",
            "reason": "The outcome/estimand differs from the original preregistered F5 task-by-attack comparison.",
        }

    result = {
        "experiment": "E14_scope_aware_revision_1",
        "evidence_class": "LABELLED_STATIC_ANALYSIS",
        "source_raw": "results/final/raw/E18_factorial.jsonl.gz",
        "label_source": "J_B (LLM-generated reference labels; not human ground truth)",
        "attack_classes_always_evaluated": list(ATTACK_CLASSES),
        "n_input_rows": len(rows),
        "n_scored_rows": sum(r.get("status") != "missing_goal_record" for r in out_rows),
        "summary": summary,
        "paired_task_level_comparison": paired,
        "raw": out_rows,
        "interpretation": (
            "This is a scope-aware offline re-analysis. It is not an executed attack test. "
            "Class-only label scopes can produce indeterminate outcomes; these are not counted as safe. "
            "The paired comparison is exploratory and cannot inherit the original F5 confirmatory status."
        ),
    }

    out_dir = Path(os.environ.get("PAMCP_REVISION_RESULTS", ROOT / "results" / "revision_1"))
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "E14_scope_aware.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "raw"}, indent=2, allow_nan=False))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()