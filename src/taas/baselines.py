"""Baselines of Table 2 re-implemented on the same registry and retriever.

* ``all_tools``       — every visible tool in the prompt (no discovery).
* ``rag_topk``        — RAG-MCP style: dense retrieval of the whole prompt, top-k tools.
* ``mcp_zero``        — MCP-Zero style: per goal request, route to the best server, then the best tool.
* ``per_subtask``     — one tool per subgoal by hybrid retrieval, no gap, no set-level checks.
* ``annotation_filter`` — eligibility by MCP's default reading of annotations (positive, ℓann).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

import numpy as np

from .goals import GoalSpec
from .retrieval import HybridRetriever


def all_tools(visible: Iterable[str]) -> list[str]:
    return sorted(visible)


def rag_topk(ret: HybridRetriever, prompt: str, pool: Sequence[str], k: int = 5) -> list[str]:
    s = ret.scores(prompt, None, pool, set(), components=("den",))
    return [t for t, _ in sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


def per_subtask(ret: HybridRetriever, spec: GoalSpec, pool: Sequence[str], k_per_goal: int = 1,
                include_native: bool = True) -> list[str]:
    out: list[str] = []
    for g in spec.goals:
        if g.optional or (not include_native and g.sigma == "native"):
            continue
        s = ret.scores(g.rendering(), None, pool, set(), components=("lex", "den"))
        for t, _ in sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))[:k_per_goal]:
            if t not in out:
                out.append(t)
    return out


def mcp_zero(ret: HybridRetriever, spec: GoalSpec, pool: Sequence[str], servers_k: int = 1) -> list[str]:
    by_srv: dict[str, list[str]] = defaultdict(list)
    for t in pool:
        by_srv[ret.contracts[t].server].append(t)
    srv_names = sorted(by_srv)
    srv_docs = [" ".join(ret.contracts[t].rendering() for t in by_srv[s])[:4000] for s in srv_names]
    sv = ret.encoder.encode(srv_docs)
    out: list[str] = []
    for g in spec.goals:
        if g.optional:
            continue
        q = ret.encoder.encode([g.rendering()])[0]
        best = [srv_names[i] for i in np.argsort(-(sv @ q))[:servers_k]]
        cand = [t for s in best for t in by_srv[s]]
        s = ret.scores(g.rendering(), None, cand, set(), components=("den",))
        if s:
            t = max(s.items(), key=lambda kv: (kv[1], kv[0]))[0]
            if t not in out:
                out.append(t)
    return out
