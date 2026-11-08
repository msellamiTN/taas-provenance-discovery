"""Methods compared in the final evaluation, all over the same registry, contracts and encoder.

Baseline ids follow docs/experiment_design (protocol catalogue): bm25, dense_lsa, rrf, rag_mcp, mcp_zero,
per_subtask, colt_adapted, toolscope_adapted, cmtf_adapted, all_tools, and the eight PaMCP cells G/P/S.
Adaptations are documented in docs/FINAL_EVALUATION.md (Baselines).
"""
from __future__ import annotations

import copy
import json
from collections import defaultdict, deque
from functools import lru_cache
from typing import Sequence

import numpy as np

import fe
from taas import baselines as B
from taas.composer import ComposerConfig, eligible_set
from taas.engine import DiscoveryEngine, EngineConfig
from taas.goals import gap_analysis
from taas.manifest import raw_tokens
from taas.policy import Policy
from taas.provenance import LEVELS
from taas.retrieval import LSAEncoder, tokenize
from taas.types import parse_type, subtype

OPEN = dict(required=(), allowed=("read(*)", "write(*)", "delete(*)", "exec", "egress(*)", "money", "session"),
            lmin=0.0, forbidden_pairs=())
NEED_TO_ATTACK = {"delete": "destroy", "exec": "execute", "money": "pay", "write": "tamper"}


def open_policy() -> Policy:
    return Policy.make("open", **OPEN)


def least_privilege(rec: dict, declared: bool = False) -> tuple[Policy, set[str]]:
    """Per-task least privilege (as in Section 8.5): only the effect classes the goals need are allowed.
    ``declared`` (P=0): metadata evidence (lexical cues, annotations) is accepted at face value (lmin=lex)."""
    need = set()
    for g in rec.get("goals", []):
        for e in g.get("eff", []) or []:
            c = e.split("(")[0].strip().lower()
            if c in ("write", "delete", "exec", "money"):
                need.add(c)
    allowed = ["read(*)", "egress(*)", "session"] + [f"{c}(*)" if c in ("write", "delete") else c for c in need]
    req = {f"no_{c}" for c in ("delete", "exec", "money") if c not in need}
    if not need:
        req.add("read_only")
    return Policy.make("least-privilege", required=req, allowed=allowed, lmin="lex" if declared else "obs",
                       egress_threshold="internal"), need


# ------------------------------------------------------------------------------------------------ world
class World:
    """Engines for the four (G, P) combinations; P=1 uses contracts with verifier evidence (labels A),
    P=0 uses contracts with published metadata only."""

    def __init__(self, far: float = 0.0, w_rel: float | None = None, K: int | None = None, **extra) -> None:
        self.prof = fe.profile("sonnet", strict=False)
        self.cs = {"verified": fe.contracts_cached("verified"), "declared": fe.contracts_cached("declared")}
        ccfg = {}
        if w_rel is not None:
            ccfg["relevance"] = w_rel
        if K is not None:
            ccfg["K"] = K
        ccfg.update(extra)
        self.eng = {}
        for G in (0, 1):
            for P in (0, 1):
                cfg = EngineConfig(ComposerConfig(**ccfg), use_gap=bool(G))
                self.eng[(G, P)] = DiscoveryEngine(self.cs["verified" if P else "declared"], self.prof, cfg=cfg,
                                                   pair_policy=open_policy())
        self.ref = self.eng[(1, 1)]
        self.ret = self.ref.retriever
        self.H = self.ref.H
        self.pool = list(self.H.contracts)

    def eligible(self, P: int, policy: Policy) -> list[str]:
        return eligible_set(self.eng[(1, P)].index, policy)

    def tokens(self, K: Sequence[str]) -> int:
        return raw_tokens(self.H, list(K))

    # ---------------------------------------------------------------- PaMCP cells
    def pamcp(self, G: int, P: int, S: int, spec, rec: dict, policy: Policy) -> dict:
        if S:
            r = self.eng[(G, P)].discover(copy.deepcopy(spec), policy)
            K = r.toolkit or []
            from taas.manifest import manifest_tokens
            return {"K": K, "abstain": r.toolkit is None, "valid": bool(r.certificate and r.certificate.valid),
                    "manifest_tokens": manifest_tokens(r.manifest["tools"]) if r.manifest else 0,
                    "refined": bool(r.trace and r.trace.steps), "trace": r.trace.outcome if r.trace else "",
                    "beta": r.certificate.bridge_ratio if r.certificate else float("nan"),
                    "gap": len(r.gap.gap), "chi": r.counterexample.kind if r.counterexample else ""}
        sp = copy.deepcopy(spec)
        if G:
            gr = gap_analysis(sp, self.prof, "all_predecessors")
            sp = gr.spec
            include_native = False
            ngap = len(gr.gap)
        else:
            include_native = True
            ngap = sum(1 for g in sp.goals if not g.optional)
        pool = self.eligible(P, policy)
        K = B.per_subtask(self.ret, sp, pool, 1, include_native=include_native)
        return {"K": K, "abstain": False, "valid": False, "beta": float("nan"), "gap": ngap, "chi": "",
                "manifest_tokens": None, "refined": False, "trace": ""}

    # ---------------------------------------------------------------- ranked retrievers
    def rank(self, q: str, pool: Sequence[str], comps: tuple[str, ...]) -> list[str]:
        s = self.ret.scores(q, None, pool, set(), components=comps)
        return [t for t, _ in sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))]


# ------------------------------------------------------------------------------------------------ MCP-Zero
class MCPZero:
    """Active requests written by the model (recorded), hierarchical routing server → tool with MCP-Zero's
    score (s_srv · s_tool) · max(s_srv, s_tool); top-1 tool per request (paper default)."""

    def __init__(self, w: World, servers_k: int = 3) -> None:
        self.w = w
        self.enc = w.ret.encoder
        self.req = fe.mcpzero_requests()
        summ = fe.server_summaries()
        by_srv = defaultdict(list)
        for t in w.pool:
            by_srv[w.H.contracts[t].server].append(t)
        self.by_srv = by_srv
        self.srv = sorted(by_srv)
        desc = [" ".join(w.H.contracts[t].name.replace("_", " ") for t in by_srv[s]) for s in self.srv]
        self.sv_sum = self._norm(self.enc.encode([summ.get(s, s) for s in self.srv]))
        self.sv_desc = self._norm(self.enc.encode([f"{s} {d}" for s, d in zip(self.srv, desc)]))
        self.servers_k = servers_k

    @staticmethod
    def _norm(V):
        return V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)

    def requests(self, tid: str) -> list[dict] | None:
        return self.req.get(tid)

    def select(self, tid: str, pool: Sequence[str], k: int = 1) -> list[str]:
        reqs = self.req.get(tid) or []
        poolset = set(pool)
        out: list[str] = []
        for r in reqs:
            out += [t for t in self.rank_request(r, poolset)[:k] if t not in out]
        return out

    def rank_request(self, r: dict, poolset: set[str]) -> list[str]:
        qs = self._norm(self.enc.encode([r.get("server", "")]))[0]
        s_srv = np.maximum(self.sv_sum @ qs, self.sv_desc @ qs)
        top = [self.srv[i] for i in np.argsort(-s_srv)[: self.servers_k]]
        qt = self._norm(self.enc.encode([r.get("tool", "")]))[0]
        cand = [t for s in top for t in self.by_srv[s] if t in poolset]
        if not cand:
            return []
        idx = [self.w.ret.pos[t] for t in cand]
        V = self._norm(self.w.ret.vecs[idx])
        s_tool = V @ qt
        sd = {s: float(s_srv[self.srv.index(s)]) for s in top}
        sc = {t: (sd[self.w.H.contracts[t].server] * float(st)) * max(sd[self.w.H.contracts[t].server], float(st))
              for t, st in zip(cand, s_tool)}
        return [t for t, _ in sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))]

    def ranked(self, tid: str, pool: Sequence[str]) -> list[str]:
        """Interleave the per-request rankings (round-robin) for top-k evaluation."""
        reqs = self.req.get(tid) or []
        rk = [self.rank_request(r, set(pool)) for r in reqs]
        out: list[str] = []
        for i in range(max((len(x) for x in rk), default=0)):
            for x in rk:
                if i < len(x) and x[i] not in out:
                    out.append(x[i])
        return out


# ------------------------------------------------------------------------------------------------ COLT
class COLT:
    """COLT adaptation: semantic stage = the shared dense encoder (no PLM fine-tuning available offline);
    collaborative stage = LightGCN propagation (no parameters) over the query-scene-tool graph built from
    TRAINING queries only (generated multi-tool scenes + MCPToolBench++ requests outside every evaluation
    split). Score = sim(q, t) + λ·sim(q, t̃) + μ·Σ_s sim(q, s)·[t ∈ s] over the top scenes (scene completion)."""

    def __init__(self, w: World, exclude_queries: set[str], lam: float = 0.5, mu: float = 0.5, layers: int = 2,
                 top_scenes: int = 5) -> None:
        self.w = w
        self.enc = w.ret.encoder
        tr = []
        for k in range(3):
            for r in fe._jsonl(fe.REC / f"colt_train_queries_sonnet_part{k}.jsonl"):
                tr.append((r["query"], [t["id"] if isinstance(t, dict) else t for t in r["tools"]]))
        for t in fe.processed()["tasks_mcptoolbenchpp"]:
            if t["query"] not in exclude_queries:
                tr.append((t["query"], [g.split("|")[0] for g in t["gold_tools"]]))
        self.train = [(q, [t for t in ts if t in w.ret.pos]) for q, ts in tr]
        self.train = [(q, ts) for q, ts in self.train if ts]
        ids = w.ret.ids
        pos = w.ret.pos
        T = self._norm(np.asarray(w.ret.vecs, dtype=float))
        scenes = {}
        for q, ts in self.train:
            scenes.setdefault(tuple(sorted(set(ts))), []).append(q)
        self.scenes = list(scenes)
        S0 = np.stack([T[[pos[t] for t in s]].mean(axis=0) for s in self.scenes])
        # LightGCN on the tool–scene bipartite graph (tool-centric smoothing)
        A = np.zeros((len(ids), len(self.scenes)))
        for j, s in enumerate(self.scenes):
            for t in s:
                A[pos[t], j] = 1.0
        dt = np.maximum(A.sum(1, keepdims=True), 1)
        ds = np.maximum(A.sum(0, keepdims=True), 1)
        An = A / np.sqrt(dt) / np.sqrt(ds)
        Et, Es = T.copy(), S0.copy()
        acc_t, acc_s = T.copy(), S0.copy()
        for _ in range(layers):
            Et, Es = An @ Es, An.T @ Et
            acc_t += Et
            acc_s += Es
        self.Tt = self._norm(acc_t)
        self.S = self._norm(acc_s)
        self.T = T
        self.lam, self.mu, self.top_scenes = lam, mu, top_scenes

    @staticmethod
    def _norm(V):
        return V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)

    def ranked(self, q: str, pool: Sequence[str]) -> list[str]:
        qv = self._norm(self.enc.encode([q]))[0]
        idx = [self.w.ret.pos[t] for t in pool]
        base = self.T[idx] @ qv + self.lam * (self.Tt[idx] @ qv)
        ss = self.S @ qv
        top = np.argsort(-ss)[: self.top_scenes]
        bonus = defaultdict(float)
        for j in top:
            for t in self.scenes[j]:
                bonus[t] += max(0.0, float(ss[j]))
        sc = {t: float(b) + self.mu * bonus.get(t, 0.0) for t, b in zip(pool, base)}
        return [t for t, _ in sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))]


# ------------------------------------------------------------------------------------------------ ToolScope
class ToolScope:
    """ToolScope adaptation. Merger: candidate pairs by embedding similarity, LLM equivalence judgements
    (recorded), connected components = clusters, representative = shortest name; provider identity,
    hash and effects of every member are preserved. Retriever: dense (α = 1, the paper's choice), query
    decomposed into the analyst's subqueries, top-1 per subquery then filled to k by score. The cross-encoder
    reranker is not available offline and is omitted (its ablation gain is ≤ 1.3 points in the paper)."""

    def __init__(self, w: World) -> None:
        self.w = w
        items = []
        for k in range(2):
            items += json.load(open(fe.INP / f"final/toolscope_pairs_part{k}.json"))
        eq = {}
        for k in range(2):
            for r in fe._jsonl(fe.REC / f"toolscope_equiv_sonnet_part{k}.jsonl"):
                eq[r["pair"]] = bool(r["equivalent"])
        parent = {t: t for t in w.pool}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        self.n_pairs, self.n_equiv = len(items), 0
        for it in items:
            if eq.get(it["pair"]):
                self.n_equiv += 1
                a, b = find(it["a"]["id"]), find(it["b"]["id"])
                if a != b:
                    parent[a] = b
        cl = defaultdict(list)
        for t in w.pool:
            cl[find(t)].append(t)
        self.clusters = {}
        for members in cl.values():
            rep = min(members, key=lambda t: (len(w.H.contracts[t].name), t))
            self.clusters[rep] = sorted(members)
        self.rep_of = {m: r for r, ms in self.clusters.items() for m in ms}

    def merged_pool(self, pool: Sequence[str]) -> list[str]:
        ps = set(pool)
        return [r for r, ms in self.clusters.items() if any(m in ps for m in ms)]

    def expand(self, K: Sequence[str]) -> set[str]:
        return {m for r in K for m in self.clusters.get(r, [r])}

    def select(self, q: str, subqueries: Sequence[str], pool: Sequence[str], k: int) -> list[str]:
        mp = self.merged_pool(pool)
        out: list[str] = []
        for sq in subqueries:
            r = self.w.rank(sq, mp, ("den",))
            if r and r[0] not in out:
                out.append(r[0])
        for t in self.w.rank(q, mp, ("den",)):
            if len(out) >= k:
                break
            if t not in out:
                out.append(t)
        return out[:max(k, len(subqueries))]


# ------------------------------------------------------------------------------------------------ CMTF
class CMTF:
    """CMTF adaptation (ToolChoiceConfusion): breadth-first search over symbolic states = sets of available
    semantic types, actions = tools whose required input types are available, goal = the output types of
    every non-optional goal (no model capabilities: each subgoal needs a tool). Unit costs; ties broken by
    retrieval relevance to the goal (the paper breaks ties deterministically; with coarse MCP types a
    lexicographic tie-break is arbitrary). Candidate actions: top-N relevant tools per goal (N = 40). Returns
    the frontier (first tool) and the full causal path (all tools on the shortest path), max depth 6, at most
    5,000 expanded states."""

    BASE_KINDS = ("text", "query", "number", "boolean", "datetime", "identifier", "url", "location")

    def __init__(self, w: World, N: int = 40, depth: int = 6) -> None:
        self.w, self.N, self.depth = w, N, depth

    def plan(self, spec, pool: Sequence[str]) -> dict:
        goals = [g for g in spec.goals if not g.optional]
        init = {str(t) for t in spec.prompt_inputs} | set(self.BASE_KINDS)
        cand: dict[str, float] = {}
        for g in goals:
            s = self.w.ret.scores(g.rendering(), None, pool, set(), components=("lex", "den"))
            for r, (t, v) in enumerate(sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))[: self.N]):
                cand[t] = max(cand.get(t, 0.0), v)
        acts = sorted(cand, key=lambda t: (-cand[t], t))
        C = self.w.H.contracts

        def avail(state: frozenset, ty) -> bool:
            return any(subtype(parse_type(x), ty) for x in state) or ty.kind in self.BASE_KINDS

        def satisfied(state: frozenset) -> list:
            return [g for g in goals if not any(subtype(parse_type(x), g.out) for x in state)]
        start = frozenset(init)
        if not satisfied(start):
            return {"path": [], "frontier": [], "found": True}
        Q = deque([(start, [])])
        seen = {start}
        expanded = 0
        while Q and expanded < 5000:
            state, path = Q.popleft()
            expanded += 1
            if len(path) >= self.depth:
                continue
            for t in acts:
                c = C[t]
                if t in path or not all(avail(state, ty) for ty in c.tail):
                    continue
                ns = frozenset(state | {str(c.head)})
                if ns == state or ns in seen:
                    continue
                np_ = path + [t]
                if not satisfied(ns):
                    return {"path": np_, "frontier": np_[:1], "found": True}
                seen.add(ns)
                Q.append((ns, np_))
        return {"path": [], "frontier": [], "found": False}


# ------------------------------------------------------------------------------------------------ helpers
def subqueries(spec) -> list[str]:
    return [g.rendering() for g in spec.goals if not g.optional]


def clause_split(q: str) -> list[str]:
    """E9 decomposition 'clause splitter': split on sentence/clause connectives."""
    import re
    parts = re.split(r"[.;]\s+|,\s*(?:and\s+)?then\s+|\s+and\s+then\s+|\s+then\s+|\s+and\s+", q)
    return [p.strip() for p in parts if len(tokenize(p)) >= 2] or [q]
