"""Algorithm 2: evidence-carrying toolkit discovery (Section 6.3).

eligibility ∩ retrieval → backward closure over intermediate types → constrained minimum-cost
cover (exact best-first branch-and-bound when |T| ≤ Nmax, constraint-aware greedy plus an
inclusion-minimality pass otherwise) → certificate C, or a typed counterexample χ.
"""
from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .bitmap_index import BitmapIndex
from .certificate import Certificate, Counterexample, certify, consumable, goal_reached
from .effects import Effect, violations
from .goals import GoalContract
from .hypergraph import Hypergraph, ModelEdge, ReachResult, effects_of, goal_match
from .model_profile import ModelProfile
from .policy import Policy
from .retrieval import HybridRetriever
from .types import SemType, parse_type, subtype


@dataclass
class ComposerConfig:
    K: int = 5                    # retrieval budget per goal / derived type (tuned on dev, E3-tune)
    depth: int = 2                # backward-closure depth d
    n_max: int = 40               # exact regime threshold Nmax
    u_min: float = 0.5            # utility floor
    w0: float = 1.0
    beta: float = 0.5
    gamma: float = 0.5
    delta: float = 0.5
    eta: float = 0.5
    zeta: float = 0.5
    type_filter: bool = True
    multimodal: bool = True
    conservative_flow: bool = True
    node_budget: int = 20000
    n_bridge: int = 50
    # Deviation (documented): Eq. (6) has no relevance term; with coarse semantic typing a minimum-cost
    # cover then prefers any type-compatible tool with fewer effects. ``relevance`` adds
    # w_rel·(1 − normalised retrieval score) to the cost; relevance=0 is the paper's Eq. (6).
    relevance: float = 10.0       # tuned on the dev split (E3-tune); 0.0 = the paper's Eq. (6)
    uncertain_ok: bool = False   # set by the χ1 repair "retrieve beyond certain typing"
    components: tuple[str, ...] = ("lex", "den", "str")


@dataclass
class ComposeResult:
    toolkit: list[str] | None
    certificate: Certificate | None
    counterexample: Counterexample | None
    candidates: list[str] = field(default_factory=list)
    regime: str = ""
    stats: dict = field(default_factory=dict)
    # Authoritative final reachability used for certification; absent on abstention.
    reachability: ReachResult | None = None


def eligible_set(index: BitmapIndex, policy: Policy) -> list[str]:
    """Line 1 / Eq. (3) (positive encoding) or Eq. (2) (closed-world encoding); Lemma 1 for V."""
    if policy.encoding == "positive":
        bm = index.eligible_positive(policy.required, policy.lmin, policy.visible)
    else:
        bm = index.eligible_closed_world(policy.forbidden, policy.lmin, visible=policy.visible)
    return index.to_ids(bm)


class CostModel:
    """Eq. (6) with every term min–max normalised to [0, 1] over the candidate set."""

    def __init__(self, H: Hypergraph, T: Iterable[str], cfg: ComposerConfig,
                 rel: dict[str, float] | None = None) -> None:
        T = list(T)
        self.cfg = cfg
        rel = rel or {}
        raw = {t: (len(H.contracts[t].eff), 1.0 - min(1.0, H.contracts[t].eff_strength()),
                   H.contracts[t].tokens, H.contracts[t].qos.price, H.contracts[t].qos.latency) for t in T}
        cols = list(zip(*raw.values())) if raw else [()] * 5
        lo = [min(c) if c else 0 for c in cols]
        hi = [max(c) if c else 0 for c in cols]
        w = (cfg.beta, cfg.gamma, cfg.delta, cfg.eta, cfg.zeta)
        self.c = {}
        for t, xs in raw.items():
            s = cfg.w0
            for i, x in enumerate(xs):
                s += w[i] * ((x - lo[i]) / (hi[i] - lo[i]) if hi[i] > lo[i] else 0.0)
            s += cfg.relevance * (1.0 - rel.get(t, 0.0))
            self.c[t] = s

    def __call__(self, t: str) -> float:
        return self.c[t]

    def total(self, K: Iterable[str]) -> float:
        return sum(self.c[t] for t in K)


def utility(H: Hypergraph, K: Iterable[str], rr: ReachResult, goals: Sequence[GoalContract]) -> float:
    """Eq. (7): ∏(1 − fail_e) · ∏ ρ_LLM(b) over the model bridges actually used."""
    u = 1.0
    for t in K:
        u *= 1.0 - H.contracts[t].qos.fail
    for g in goals:
        typ = goal_reached(rr, g, H, True)
        typ = typ[1:] if typ and typ.startswith("~") else typ
        d = rr.derivations.get(typ) if typ else None
        if d is not None and d.kind == "model":
            u *= d.rho
    for b in rr.bridges:
        u *= b.rho
    return u


class Composer:
    def __init__(self, H: Hypergraph, index: BitmapIndex, retriever: HybridRetriever, profile: ModelProfile,
                 cfg: ComposerConfig | None = None) -> None:
        self.H, self.index, self.ret, self.profile = H, index, retriever, profile
        self.cfg = cfg or ComposerConfig()

    # ------------------------------------------------------------------ helpers
    def model_edges(self, goals: Sequence[GoalContract]) -> list[ModelEdge]:
        """Class-typed model edges for goals covered by the profile (Cov(e^LLM))."""
        out = []
        for g in goals:
            if g.sigma == "native":
                out.append(ModelEdge(g.cls, tuple(g.inputs), g.out,
                                     self.profile.rho(g.cls, g.n, g.lang, g.exactness), g.id))
        return out

    def _reach(self, K: Iterable[str], X, medges) -> ReachResult:
        return self.H.reach(K, X, medges, self.profile, self.cfg.n_bridge)

    def _sufficient(self, rr: ReachResult, goals: Sequence[GoalContract]) -> bool:
        return all(goal_reached(rr, g, self.H, self.cfg.uncertain_ok) is not None for g in goals if not g.optional)

    def _check_add(self, e: str, K: Sequence[str], X, medges, policy: Policy) -> Counterexample | None:
        H = self.H
        for e2 in K:
            why = H.is_forbidden(e, e2)
            if why:
                return Counterexample("chi5", None, "E/F", {"pair": [e, e2], "reason": why})
        effs = effects_of(H, list(K) + [e])
        bad = violations(effs, policy.allowed)
        if bad:
            return Counterexample("chi2", None, "E", {"tool": e, "outside_A": sorted(map(str, bad))})
        rr = H.reach(list(K) + [e], X, medges, self.profile, self.cfg.n_bridge, policy)
        fl = H.flow_violations(list(K) + [e], rr, policy, self.cfg.conservative_flow)
        if fl:
            return Counterexample("chi5", None, "L", {"violations": fl})
        c = H.contracts[e]
        if not consumable(c, self.cfg.multimodal) or (policy.credentials is not None and
                                                       any(r not in policy.credentials for r in c.req)):
            return Counterexample("chi1", None, "C/P", {"tool": e})
        return None

    # ---------------------------------------------------------------- candidates
    def candidates(self, gap: Sequence[GoalContract], goals: Sequence[GoalContract], X: Sequence[SemType],
                   policy: Policy, elig: Sequence[str], medges) -> tuple[list[str], list[Counterexample], dict]:
        """Lines 2–16: per-goal retrieval and backward closure over intermediate types."""
        cfg = self.cfg
        R0 = self._reach([], X, medges).types
        T: list[str] = []
        chis: list[Counterexample] = []
        per_goal: dict[str, list[str]] = {}
        self.rel: dict[str, float] = {}
        for g in gap:
            got = self.ret.retrieve(g.rendering(), g.out, elig, R0, cfg.K, cfg.type_filter,
                                    cfg.components, matcher=lambda c, g=g: goal_match(c, g, cfg.uncertain_ok))
            top = max((v for _, v in got), default=0.0) or 1.0
            for t, v in got:
                self.rel[t] = max(self.rel.get(t, 0.0), v / top)
            Tg = [t for t, _ in got]
            if not Tg:
                any_prod = any(goal_match(c, g, cfg.uncertain_ok) for c in self.H.contracts.values())
                chis.append(Counterexample("chi2" if any_prod else "chi1", g.id, "S",
                                           {"goal_out": str(g.out), "eligible": len(elig)}))
            per_goal[g.id] = Tg
            T += [t for t in Tg if t not in T]
        if chis:
            return T, chis, per_goal
        derived: set[SemType] = set()
        produced = {self.H.contracts[t].head for t in T}
        frontier = {th for t in T for th in self.H.contracts[t].tail
                    if self.H.tail_satisfied(th, R0, self.profile, cfg.n_bridge) is None}
        for _ in range(cfg.depth):
            Tn: list[str] = []
            for th in frontier:
                derived.add(th)
                got = self.ret.retrieve(f"{th.kind} {th.domain or ''}", th, elig, R0, cfg.K, True, cfg.components)
                top = max((v for _, v in got), default=0.0) or 1.0
                for t, v in got:
                    self.rel[t] = max(self.rel.get(t, 0.0), v / top)
                Tn += [t for t, _ in got if t not in T and t not in Tn]
            T += Tn
            produced |= {self.H.contracts[t].head for t in Tn}
            frontier = {th for t in Tn for th in self.H.contracts[t].tail
                        if self.H.tail_satisfied(th, R0, self.profile, cfg.n_bridge) is None
                        and not any(subtype(p, th) for p in produced)}
            if not frontier:
                break
        per_goal["_derived"] = sorted(map(str, derived))
        return T, [], per_goal

    # -------------------------------------------------------------------- search
    def compose(self, gap: Sequence[GoalContract], goals: Sequence[GoalContract], X: Sequence[SemType],
                policy: Policy) -> ComposeResult:
        t0 = time.perf_counter()
        cfg = self.cfg
        X = [parse_type(x) for x in X]
        elig = eligible_set(self.index, policy)
        medges = self.model_edges(goals)
        T, chis, per_goal = self.candidates(gap, goals, X, policy, elig, medges)
        stats = {"eligible": len(elig), "candidates": len(T), "per_goal": per_goal}
        if chis:
            chi = max(chis, key=lambda c: c.priority())
            return ComposeResult(None, None, chi, T, "", stats | {"time_s": time.perf_counter() - t0})
        cost = CostModel(self.H, T, cfg, getattr(self, "rel", {}))
        if len(T) > cfg.n_max:
            res = self._greedy(T, gap, goals, X, policy, medges, cost)
            regime = "greedy"
        else:
            res = self._branch_and_bound(T, gap, goals, X, policy, medges, cost)
            regime = "exact"
            if res[0] is None and res[2] == "budget":
                res = self._greedy(T, gap, goals, X, policy, medges, cost)
                regime = "greedy(after-budget)"
        K, chi, info = res
        stats |= {"time_s": time.perf_counter() - t0, "search": info}
        if K is None:
            return ComposeResult(None, None, chi, T, regime, stats)
        rr = self.H.reach(K, X, medges, self.profile, cfg.n_bridge, policy)
        cert = certify(self.H, K, list(goals), X, policy, medges, self.profile, regime=regime,
                       cost=cost.total(K), util=utility(self.H, K, rr, goals), multimodal=cfg.multimodal,
                       conservative_flow=cfg.conservative_flow, n_bridge=cfg.n_bridge,
                       uncertain=cfg.uncertain_ok)
        return ComposeResult(sorted(K), cert, None, T, regime, stats, rr)

    def _branch_and_bound(self, T, gap, goals, X, policy, medges, cost):
        """Lines 19–38: best-first search on Σ cost; first sufficient minimal state is optimal."""
        cfg = self.cfg
        counter = itertools.count()
        start = ()
        rr0 = self._reach([], X, medges)
        heap = [(0.0, next(counter), start)]
        seen = {frozenset()}
        recorded: list[Counterexample] = []
        best, best_cost, nodes = None, float("inf"), 0
        reach_cache: dict[frozenset, ReachResult] = {frozenset(): rr0}
        while heap:
            c, _, K = heapq.heappop(heap)
            if c >= best_cost:
                break
            nodes += 1
            if nodes > cfg.node_budget:
                return None, None, "budget"
            rr = reach_cache[frozenset(K)]
            if self._sufficient(rr, goals) and utility(self.H, K, rr, goals) >= cfg.u_min:
                # (M): skip non-minimal states (a cheaper subset is explored first)
                if any(self._sufficient(self._reach([x for x in K if x != e], X, medges), goals) for e in K):
                    continue
                best, best_cost = list(K), c
                continue
            for e in T:
                if e in K:
                    continue
                ce = self.H.contracts[e]
                if not all(self.H.tail_satisfied(th, rr.types, self.profile, cfg.n_bridge) for th in ce.tail):
                    continue
                if ce.head.kind != "none" and not any(e.cls in ("write", "delete", "exec", "money", "egress") for e in ce.eff) \
                        and any(subtype(s, ce.head) and subtype(ce.head, s) for s in map(parse_type, rr.tool_types)):
                    continue  # adds no new type or effect: never part of a minimal sufficient toolkit
                K2 = tuple(sorted(K + (e,)))
                fk = frozenset(K2)
                if fk in seen:
                    continue
                chi = self._check_add(e, K, X, medges, policy)
                if chi is not None:
                    recorded.append(chi)
                    continue
                seen.add(fk)
                reach_cache[fk] = self._reach(K2, X, medges)
                heapq.heappush(heap, (c + cost(e), next(counter), K2))
        if best is None:
            chi = max(recorded, key=lambda c: c.priority()) if recorded else \
                Counterexample("chi1", self._first_unreached(goals, rr0, T, X, medges), "S",
                               {"candidates": len(T)})
            if chi.kind == "chi1" and chi.goal is None:
                chi.goal = self._first_unreached(goals, rr0, T, X, medges)
            return None, chi, {"nodes": nodes}
        return best, None, {"nodes": nodes, "cost": best_cost}

    def _first_unreached(self, goals, rr0, T, X, medges) -> str | None:
        rr = self._reach(T, X, medges)
        for g in goals:
            if not g.optional and goal_reached(rr, g, self.H, self.cfg.uncertain_ok) is None:
                return g.id
        return None

    def _greedy(self, T, gap, goals, X, policy, medges, cost):
        """Constraint-aware greedy cover + inclusion-minimality pass (no approximation claim)."""
        cfg = self.cfg
        K: list[str] = []
        rr = self._reach([], X, medges)
        recorded: list[Counterexample] = []
        while not self._sufficient(rr, goals):
            best, best_ratio, best_rr = None, -1.0, None
            for e in T:
                if e in K:
                    continue
                ce = self.H.contracts[e]
                if not all(self.H.tail_satisfied(th, rr.types, self.profile, cfg.n_bridge) for th in ce.tail):
                    continue
                if ce.head.kind != "none" and not any(x.cls in ("write", "delete", "exec", "money", "egress") for x in ce.eff) \
                        and any(subtype(s, ce.head) and subtype(ce.head, s) for s in map(parse_type, rr.tool_types)):
                    continue
                chi = self._check_add(e, K, X, medges, policy)
                if chi is not None:
                    recorded.append(chi)
                    continue
                rr2 = self._reach(K + [e], X, medges)
                gain = sum(1 for g in goals if goal_reached(rr2, g, self.H, cfg.uncertain_ok)
                           and not goal_reached(rr, g, self.H, cfg.uncertain_ok))
                gain += 0.5 * len(rr2.types - rr.types)
                ratio = gain / cost(e)
                if ratio > best_ratio:
                    best, best_ratio, best_rr = e, ratio, rr2
            if best is None:
                chi = max(recorded, key=lambda c: c.priority()) if recorded else \
                    Counterexample("chi1", self._first_unreached(goals, rr, T, X, medges), "S", {"regime": "greedy"})
                return None, chi, {"regime": "greedy"}
            K.append(best)
            rr = best_rr
        for e in sorted(list(K), key=lambda t: -cost(t)):
            rest = [x for x in K if x != e]
            if self._sufficient(self._reach(rest, X, medges), goals):
                K = rest
        rr = self._reach(K, X, medges)
        if utility(self.H, K, rr, goals) < cfg.u_min:
            return None, Counterexample("chi4", None, "util", {"util": utility(self.H, K, rr, goals)}), {}
        return K, None, {"regime": "greedy", "size": len(K)}
