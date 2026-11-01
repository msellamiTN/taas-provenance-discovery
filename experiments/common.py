"""Shared helpers for the experiments (paths, loading recorded LLM outputs, metrics, I/O)."""
from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from taas.data.registries import load_processed, tasks_from_processed  # noqa: E402
from taas.goals import GoalSpec, parse_goal_spec  # noqa: E402
from taas.llm.backends import ReplayAnalyst  # noqa: E402
from taas.model_profile import ModelProfile  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
SEEDS = [0, 1, 2, 3, 4]


def save(name: str, obj) -> Path:
    p = RESULTS / f"{name}.json"
    json.dump(obj, open(p, "w"), indent=1, default=str)
    return p


def banner(msg: str) -> None:
    print("\n" + "=" * 78 + f"\n{msg}\n" + "=" * 78, flush=True)


def analyst(model: str = "sonnet") -> ReplayAnalyst:
    if model == "sonnet":
        return ReplayAnalyst(["data/llm_records/analyst_sonnet_A.jsonl", "data/llm_records/analyst_sonnet_B.jsonl"],
                             "claude-sonnet (recorded)")
    return ReplayAnalyst([f"data/llm_records/analyst_{model}.jsonl"], f"claude-{model} (recorded)")


def profile(model: str = "sonnet", **overrides) -> ModelProfile:
    p = ModelProfile.load(ROOT / f"data/processed/profile_{model}.json")
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def prompts() -> list[dict]:
    return json.load(open(ROOT / "data/llm_inputs/analyst_prompts.json"))


def gold_sets(task_gold: list[str]) -> list[set[str]]:
    """Gold tools as alternative sets (ambiguous names resolve to any of several server::name ids)."""
    return [set(g.split("|")) for g in task_gold]


def gold_recall(toolkit: Iterable[str], gold: list[set[str]]) -> float:
    if not gold:
        return float("nan")
    K = set(toolkit)
    return sum(1 for alts in gold if alts & K) / len(gold)


def gold_precision(toolkit: Iterable[str], gold: list[set[str]]) -> float:
    K = list(toolkit)
    if not K:
        return float("nan")
    flat = set().union(*gold) if gold else set()
    return sum(1 for t in K if t in flat) / len(K)


def mean_ci(xs: Iterable[float]) -> dict:
    xs = [x for x in xs if x == x]
    if not xs:
        return {"mean": float("nan"), "ci95": float("nan"), "n": 0}
    a = np.asarray(xs, dtype=float)
    se = a.std(ddof=1) / np.sqrt(len(a)) if len(a) > 1 else 0.0
    return {"mean": float(a.mean()), "ci95": float(1.96 * se), "n": len(a)}


def bootstrap_ci(xs: Iterable[float], B: int = 2000, seed: int = 0) -> tuple[float, float]:
    xs = np.asarray([x for x in xs if x == x], dtype=float)
    if len(xs) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    ms = rng.choice(xs, (B, len(xs))).mean(axis=1)
    return float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))


class Timer:
    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.s = time.perf_counter() - self.t
