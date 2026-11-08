"""Shared library of the final PaMCP evaluation (protocol E1-E22, see docs/FINAL_EVALUATION_PLAN.md).

Evidence classes attached to every result file:
* MEASURED   — deterministic computation on registry/benchmark data, no labels involved;
* LABELLED   — scored against reference labels B (independent LLM labelling; not human);
* SIMULATED  — evidence or attackers simulated (from labels A) and scored against labels B;
* SYNTHETIC  — generated registries/tasks;
* BLOCKED    — requires human annotation, executed MCP servers or an execution oracle.
Labels A (data/llm_records/silver_labels.json) drive the engine's typing and the simulated verifier.
Labels B (data/llm_records/reference_labels_opus_part*.jsonl) are only used for scoring.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from taas.effects import parse_effects  # noqa: E402
from taas.goals import parse_goal_spec  # noqa: E402
from taas.model_profile import ModelProfile  # noqa: E402
from taas.provenance import EvidenceStore  # noqa: E402
from taas.realreg import Truth, build_contracts, raw_registry, truth  # noqa: E402
from taas.simulation import Verifier  # noqa: E402

RES = ROOT / "results" / "final"
RES.mkdir(parents=True, exist_ok=True)
REC = ROOT / "data" / "llm_records"
INP = ROOT / "data" / "llm_inputs"


# ----------------------------------------------------------------------------------------------- manifest
def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # pragma: no cover
        return "unknown"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def save(name: str, obj: dict, evidence: str | dict, inputs: Sequence[str] = (), notes: str = "") -> Path:
    files = [ROOT / "data/processed/registry_merged.json"] + [ROOT / i for i in inputs]
    out = {"experiment": name, "evidence": evidence, "notes": notes,
           "manifest": {"commit": git_commit(), "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "python": sys.version.split()[0],
                        "inputs": {str(f.relative_to(ROOT)): sha256(f) for f in files if f.exists()}},
           **obj}
    p = RES / f"{name}.json"
    json.dump(out, open(p, "w"), indent=1, default=_default)
    return p


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


# ----------------------------------------------------------------------------------------------- data
@lru_cache(maxsize=1)
def processed() -> dict:
    return json.load(open(ROOT / "data/processed/registry_merged.json"))


@lru_cache(maxsize=1)
def raw():
    return raw_registry()


def reg() -> dict[str, dict]:
    return {t["id"]: t for t in processed()["registry"]}


@lru_cache(maxsize=1)
def labels_A() -> dict[str, Truth]:
    return truth()


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in open(p) if x.strip()] if p.exists() else []


@lru_cache(maxsize=1)
def labels_B_raw() -> dict[str, dict]:
    out = {}
    for k in range(3):
        for r in _jsonl(REC / f"reference_labels_opus_part{k}.jsonl"):
            out[r["id"]] = r
    return out


def _b_effects(r: dict) -> list[str]:
    cls = set(r.get("classes") or [])
    effs = []
    if "read" in cls:
        effs.append("read(api)" if cls & {"egress", "egress_any"} else "read(local)")
    for c, e in (("write", "write(*)"), ("delete", "delete(*)"), ("exec", "exec"), ("money", "money"),
                 ("session", "session"), ("egress", "egress(api)"), ("egress_any", "egress(*)")):
        if c in cls:
            effs.append(e)
    return effs or ["read(local)"]


@lru_cache(maxsize=1)
def labels_B() -> dict[str, Truth]:
    out = {}
    for t, r in labels_B_raw().items():
        effs = parse_effects(_b_effects(r))
        cls = r.get("classes") or []
        out[t] = Truth(effs, bool(r.get("state")) or bool(set(cls) & {"write", "delete", "exec", "money"}),
                       bool(r.get("private")), "other")
    return out


def tasks_live() -> list[dict]:
    """LiveMCPBench test tasks with gold groups (alternatives) and the analyst prompt id."""
    out = []
    for t in processed()["tasks_livemcpbench"]:
        out.append({"id": t["id"], "query": t["query"], "category": t["category"],
                    "gold": [set(g.split("|")) for g in t["gold_tools"]]})
    return out


def tasks_dev() -> list[dict]:
    pp = {t["id"]: t for t in processed()["tasks_mcptoolbenchpp"]}
    ps = json.load(open(INP / "analyst_prompts.json"))
    return [{"id": p["id"], "query": p["query"], "category": p["category"],
             "gold": [set(g.split("|")) for g in pp[p["id"]]["gold_tools"]]} for p in ps
            if p["source"] == "MCPToolBench++"]


def tasks_e8_sample() -> list[dict]:
    s = json.load(open(INP / "final/e8_sample.json"))
    return [{"id": x["id"], "query": x["query"], "category": x["category"],
             "gold": [set(g.split("|")) for g in x["gold_tools"]]} for x in s]


def tasks_pp_all() -> list[dict]:
    return [{"id": t["id"], "query": t["query"], "category": t["category"],
             "gold": [set(g.split("|")) for g in t["gold_tools"]]} for t in processed()["tasks_mcptoolbenchpp"]]


@lru_cache(maxsize=2)
def analyst_records(model: str = "sonnet") -> dict[str, dict]:
    files = (["analyst_sonnet_A.jsonl", "analyst_sonnet_B.jsonl"] + [f"analyst_sonnet_e8_part{k}.jsonl"
                                                                       for k in range(3)]
             if model == "sonnet" else ["analyst_haiku.jsonl"])
    out = {}
    for f in files:
        for r in _jsonl(REC / f):
            out[r["id"]] = r
    return out


def spec_for(task: dict, model: str = "sonnet"):
    rec = analyst_records(model).get(task["id"])
    if rec is None:
        return None, None
    return parse_goal_spec(copy.deepcopy(rec), task["query"]), rec


@lru_cache(maxsize=1)
def mcpzero_requests() -> dict[str, list[dict]]:
    out = {}
    for k in range(4):
        for r in _jsonl(REC / f"mcpzero_requests_sonnet_part{k}.jsonl"):
            out[r["id"]] = r.get("requests") or []
    return out


@lru_cache(maxsize=1)
def server_summaries() -> dict[str, str]:
    return {r["server"]: r["summary"] for r in _jsonl(REC / "mcpzero_server_summaries_sonnet.jsonl")}


def profile(model: str = "sonnet", strict: bool = False) -> ModelProfile:
    p = ModelProfile.load(ROOT / f"data/processed/profile_{model}.json")
    p.strict = strict
    return p


# ----------------------------------------------------------------------------------------------- evidence
def verifier_store(J: dict[str, Truth], far: float = 0.0, frr: float = 0.0, runnable: float = 1.0, seed: int = 0,
                   attest: float = 0.3, raw_tools=None) -> EvidenceStore:
    return Verifier(far=far, frr=frr, runnable=runnable, seed=seed).run(raw_tools or raw(), J, attest=attest)


@lru_cache(maxsize=4)
def contracts_cached(kind: str):
    if kind == "verified":
        return build_contracts(raw(), verifier_store(labels_A()))
    return build_contracts(raw(), None)


# ----------------------------------------------------------------------------------------------- metrics
def group_recall(K: Iterable[str], gold: list[set[str]]) -> float:
    K = set(K)
    return sum(1 for g in gold if g & K) / len(gold) if gold else float("nan")


def complete(K: Iterable[str], gold: list[set[str]]) -> float:
    K = set(K)
    return float(all(g & K for g in gold)) if gold else float("nan")


def set_precision(K: Sequence[str], gold: list[set[str]]) -> float:
    if not K:
        return float("nan")
    allg = set().union(*gold) if gold else set()
    return sum(1 for t in K if t in allg) / len(K)


def hit_at(ranked: Sequence[str], gold: list[set[str]], k: int) -> float:
    allg = set().union(*gold) if gold else set()
    return float(any(t in allg for t in ranked[:k]))


def mrr_at(ranked: Sequence[str], gold: list[set[str]], k: int = 10) -> float:
    allg = set().union(*gold) if gold else set()
    for i, t in enumerate(ranked[:k], start=1):
        if t in allg:
            return 1.0 / i
    return 0.0


# ----------------------------------------------------------------------------------------------- statistics
def nanmean(xs) -> float:
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return float(np.mean(xs)) if xs else float("nan")


def boot_ci(xs, B: int = 4000, seed: int = 0, clusters: Sequence | None = None) -> tuple[float, float]:
    """Percentile bootstrap of the mean; resampling unit = item, or cluster when ``clusters`` is given."""
    xs = np.asarray([x for x in xs], dtype=float)
    ok = ~np.isnan(xs)
    if ok.sum() == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    if clusters is None:
        v = xs[ok]
        idx = rng.integers(0, len(v), size=(B, len(v)))
        m = v[idx].mean(axis=1)
    else:
        cl = np.asarray(clusters)[ok]
        v = xs[ok]
        uc = np.unique(cl)
        groups = [v[cl == c] for c in uc]
        sums = np.array([g.sum() for g in groups])
        cnts = np.array([len(g) for g in groups])
        idx = rng.integers(0, len(uc), size=(B, len(uc)))
        m = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def signflip(d, B: int = 20000, seed: int = 0, alternative: str = "two-sided", shift: float = 0.0) -> float:
    """Paired sign-flip permutation test on differences d (exact when ≤ 16 non-zero pairs)."""
    d = np.asarray([x for x in d if not (isinstance(x, float) and math.isnan(x))], dtype=float) + shift
    nz = d[d != 0]
    if len(nz) == 0:
        return 1.0
    obs = nz.mean()
    if len(nz) <= 16:
        signs = np.array(np.meshgrid(*[[-1, 1]] * len(nz))).reshape(len(nz), -1).T
    else:
        rng = np.random.default_rng(seed)
        signs = rng.choice([-1, 1], size=(B, len(nz)))
    null = (signs * np.abs(nz)).mean(axis=1)
    if alternative == "greater":
        return float((np.sum(null >= obs - 1e-12) + 1) / (len(null) + 1))
    if alternative == "less":
        return float((np.sum(null <= obs + 1e-12) + 1) / (len(null) + 1))
    return float((np.sum(np.abs(null) >= abs(obs) - 1e-12) + 1) / (len(null) + 1))


def paired(a, b, margin: float | None = None, seed: int = 0) -> dict:
    """a, b: matched per-task outcomes (method, comparator). Two-sided sign-flip test of a-b, bootstrap CI;
    with ``margin`` also a one-sided non-inferiority test of H0: mean(a-b) <= -margin."""
    d = [x - y for x, y in zip(a, b) if not (math.isnan(x) or math.isnan(y))]
    out = {"n": len(d), "nonzero": int(sum(1 for x in d if x != 0)), "mean_a": nanmean(a), "mean_b": nanmean(b),
           "diff": float(np.mean(d)) if d else float("nan"), "ci": boot_ci(d, seed=seed),
           "p": signflip(d, seed=seed)}
    if margin is not None:
        out["margin"] = margin
        out["p_noninferior"] = signflip(d, seed=seed, alternative="greater", shift=margin)
    return out


def holm(ps: dict[str, float]) -> dict[str, float]:
    ks = sorted(ps, key=ps.get)
    out, run = {}, 0.0
    for r, k in enumerate(ks):
        run = max(run, min(1.0, (len(ks) - r) * ps[k]))
        out[k] = run
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def kappa(a: Sequence, b: Sequence) -> float:
    cats = sorted(set(a) | set(b), key=str)
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((sum(1 for x in a if x == c) / n) * (sum(1 for y in b if y == c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def summarise(rows: list[dict], by: Sequence[str], metrics: Sequence[str], cluster: str | None = None) -> dict:
    keys = sorted({tuple(r[b] for b in by) for r in rows}, key=str)
    out = {}
    for k in keys:
        sel = [r for r in rows if tuple(r[b] for b in by) == k]
        m = {}
        for x in metrics:
            vals = [r[x] for r in sel]
            m[x] = {"mean": nanmean(vals), "ci": boot_ci(vals, clusters=[r[cluster] for r in sel] if cluster else None),
                    "n": int(sum(1 for v in vals if not (isinstance(v, float) and math.isnan(v))))}
        out["|".join(str(v) for v in k)] = m
    return out


def timer():
    t0 = time.perf_counter()
    return lambda: time.perf_counter() - t0


RNG = random.Random(7)
