"""The deployed model as conditional, class-typed capability hyperedges (Definition 6).

ρ_LLM(c, n, lang, ε, m) ∈ [0, 1] is measured per model version on calibration sets stratified
by n (log-spaced buckets). The four rules of Section 5 are implemented:

1. classes requiring exactness have ρ fixed below τ beyond a small n (``exact_n_max``);
2. between buckets ρ is interpolated isotonically (non-increasing in n, and lower for
   exact than for tolerant use); beyond the largest measured n it is extrapolated
   conservatively; an unmeasured class or script family is *unknown* → 0 (not native);
3. the executing model's profile is used (the profile object is keyed by model id);
4. ρ enters the objective through util(K) (Eq. 7) in the composer.

``priors`` holds unmeasured cells declared by the operator (provenance ``prior``); they are
ignored in ``strict`` mode, which is the paper's rule; the non-strict mode is an ablation.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MODEL_CLASSES = ("classify", "extract", "summarise", "translate", "convert_format", "write", "plan",
                 "synthesise", "aggregate", "compute_exact", "count", "compare", "answer")
EXACT_CLASSES = frozenset({"compute_exact", "count", "aggregate_exact"})
# goal/tool classes that by nature require a tool (they cross the model boundary)
EXTERNAL_CLASSES = frozenset({"retrieve", "search", "fetch_web", "store", "send", "transact", "execute",
                              "navigate_browser", "render_media", "create_document", "edit_document", "random"})


def isotonic_decreasing(xs: list[float], ys: list[float], ws: list[float] | None = None) -> list[float]:
    """Pool-adjacent-violators for a non-increasing fit (xs sorted ascending)."""
    ws = ws or [1.0] * len(ys)
    blocks = [[y, w, 1] for y, w in zip(ys, ws)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] < blocks[i + 1][0] - 1e-12:  # violation of non-increasing
            y = (blocks[i][0] * blocks[i][1] + blocks[i + 1][0] * blocks[i + 1][1]) / (blocks[i][1] + blocks[i + 1][1])
            blocks[i] = [y, blocks[i][1] + blocks[i + 1][1], blocks[i][2] + blocks[i + 1][2]]
            del blocks[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    out: list[float] = []
    for y, _, k in blocks:
        out += [y] * k
    return out


@dataclass
class ClassProfile:
    buckets: list[int]                 # measured n (ascending)
    acc: list[float]                   # isotonic fit per bucket
    raw: list[float]                   # raw accuracy per bucket
    count: list[int]                   # items per bucket
    langs: tuple[str, ...] = ("en",)
    source: str = "measured"

    def at(self, n: float, extrapolation: str = "decay") -> float:
        if n <= self.buckets[0]:
            return self.acc[0]
        ln = math.log(n)
        lb = [math.log(b) for b in self.buckets]
        if n <= self.buckets[-1]:
            return float(np.interp(ln, lb, self.acc))
        if extrapolation == "zero":
            return 0.0
        # conservative: continue the last log-slope (never increasing), halve per decade otherwise
        if len(self.acc) >= 2 and self.acc[-1] < self.acc[-2]:
            slope = (self.acc[-1] - self.acc[-2]) / (lb[-1] - lb[-2])
            return max(0.0, self.acc[-1] + slope * (ln - lb[-1]))
        return self.acc[-1] * 0.5 ** ((ln - lb[-1]) / math.log(10))


@dataclass
class ModelProfile:
    model_id: str
    tau: float = 0.9
    classes: dict[str, ClassProfile] = field(default_factory=dict)
    priors: dict[str, float] = field(default_factory=dict)
    exact_n_max: int = 20
    context_budget_tokens: int = 150_000
    tokens_per_item: int = 25
    strict: bool = True
    class_map: dict[str, str] = field(default_factory=lambda: {
        "aggregate": "aggregate_sum", "compute_exact": "aggregate_sum", "count": "count",
        "classify": "classify", "extract": "extract", "compare": "classify", "answer": "extract"})

    def rho(self, c: str, n: float, lang: str = "en", exactness: str = "tolerant") -> float:
        """ρ_LLM(c, n, lang, ε, m)."""
        n = max(1.0, float(n or 1))
        if n * self.tokens_per_item > self.context_budget_tokens:
            return 0.0
        if c in EXTERNAL_CLASSES:
            return 0.0
        if (exactness == "exact" or c in EXACT_CLASSES) and n > self.exact_n_max:
            meas = self._measured(c, n, lang)
            # rule 1: exact classes beyond a small n are never native, whatever was measured
            return min(meas if meas is not None else 0.0, self.tau - 1e-6)
        meas = self._measured(c, n, lang)
        if meas is not None:
            return meas
        if self.strict:
            return 0.0  # rule 2: unmeasured ⇒ unknown ⇒ not native
        return self.priors.get(c, 0.0)

    def _measured(self, c: str, n: float, lang: str) -> float | None:
        key = self.class_map.get(c, c)
        cp = self.classes.get(key)
        if cp is None or lang not in cp.langs:
            return None
        return cp.at(n)

    def covers(self, c: str, n: float, lang: str = "en", exactness: str = "tolerant") -> bool:
        return self.rho(c, n, lang, exactness) >= self.tau

    # ----------------------------------------------------------- persistence
    @staticmethod
    def from_calibration(model_id: str, records: list[dict], tau: float = 0.9, **kw) -> "ModelProfile":
        """records: [{class, n, correct}] → isotonic per-class profile."""
        by: dict[str, dict[int, list[int]]] = {}
        for r in records:
            by.setdefault(r["class"], {}).setdefault(int(r["n"]), []).append(int(bool(r["correct"])))
        classes = {}
        for c, d in by.items():
            bs = sorted(d)
            raw = [sum(d[b]) / len(d[b]) for b in bs]
            cnt = [len(d[b]) for b in bs]
            classes[c] = ClassProfile(bs, isotonic_decreasing([float(b) for b in bs], raw, [float(x) for x in cnt]),
                                      raw, cnt)
        return ModelProfile(model_id, tau, classes, **kw)

    def to_json(self) -> dict:
        return {"model_id": self.model_id, "tau": self.tau, "exact_n_max": self.exact_n_max, "strict": self.strict,
                "priors": self.priors,
                "classes": {c: vars(cp) for c, cp in self.classes.items()}}

    @staticmethod
    def from_json(d: dict) -> "ModelProfile":
        classes = {c: ClassProfile(**{k: (tuple(v) if k == "langs" else v) for k, v in cp.items()})
                   for c, cp in d["classes"].items()}
        return ModelProfile(d["model_id"], d["tau"], classes, d.get("priors", {}), d.get("exact_n_max", 20),
                            strict=d.get("strict", True))

    @staticmethod
    def load(path: str | Path) -> "ModelProfile":
        return ModelProfile.from_json(json.load(open(path)))


DEFAULT_PRIORS = {"summarise": 0.92, "write": 0.95, "plan": 0.93, "synthesise": 0.92, "translate": 0.93,
                  "convert_format": 0.95, "compare": 0.9, "answer": 0.9}
