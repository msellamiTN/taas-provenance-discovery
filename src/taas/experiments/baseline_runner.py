"""Executable retrieval/planning baseline adapters for the PaMCP evaluation workbench.

External-method adapters are explicitly labelled as adaptations. This module does not
claim exact reproductions of COLT, ToolScope, CMTF or AutoTool.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from taas.baselines import all_tools, mcp_zero, per_subtask, rag_topk
from taas.effects import Effect, within
from taas.experiments.baseline_catalog import baseline_index
from taas.goals import GoalSpec
from taas.policy import Policy
from taas.retrieval import HybridRetriever, tokenize
from taas.types import SemType, parse_type, subtype


@dataclass
class BaselineResult:
    baseline_id: str
    status: str
    selected_tools: list[str] = field(default_factory=list)
    ranking: list[dict[str, Any]] = field(default_factory=list)
    stepwise_frontiers: list[dict[str, Any]] = field(default_factory=list)
    merged_groups: list[list[str]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rank(scores: Mapping[str, float], k: int) -> list[tuple[str, float]]:
    return sorted(scores.items(), key=lambda item: (-float(item[1]), item[0]))[:max(0, k)]


def _tool_ranking(scores: Sequence[tuple[str, float]]) -> list[dict[str, Any]]:
    return [{"tool_id": tool, "score": float(score), "rank": i + 1}
            for i, (tool, score) in enumerate(scores)]


def _minmax(scores: Mapping[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return {key: 0.0 for key in scores}
    return {key: (value - lo) / (hi - lo) for key, value in scores.items()}


def _bm25(retriever: HybridRetriever, query: str, pool: Sequence[str], k: int) -> BaselineResult:
    scores = retriever.scores(query, None, pool, set(), components=("lex",))
    ranked = _rank(scores, k)
    return BaselineResult("bm25", "completed", [t for t, _ in ranked], _tool_ranking(ranked),
                          details={"ranker": "repository BM25", "candidate_count": len(pool)})


def _dense(retriever: HybridRetriever, query: str, pool: Sequence[str], k: int,
           baseline_id: str = "dense_lsa") -> BaselineResult:
    scores = retriever.scores(query, None, pool, set(), components=("den",))
    ranked = _rank(scores, k)
    return BaselineResult(baseline_id, "completed", [t for t, _ in ranked], _tool_ranking(ranked),
                          details={"encoder": type(retriever.encoder).__name__,
                                   "surrogate": type(retriever.encoder).__name__ == "LSAEncoder",
                                   "candidate_count": len(pool)})



def _rag_multiquery(
    retriever: HybridRetriever, prompt: str, spec: GoalSpec, pool: Sequence[str], k: int,
    rrf_k0: int = 60,
) -> BaselineResult:
    """Global-context multi-query dense retrieval with reciprocal-rank fusion."""
    queries = [prompt] + [g.rendering() for g in spec.goals if not g.optional]
    fused: dict[str, float] = {tool: 0.0 for tool in pool}
    for query in queries:
        scores = retriever.scores(query, None, pool, set(), components=("den",))
        ranked = sorted(scores.items(), key=lambda item: (-float(item[1]), item[0]))
        for rank, (tool, _score) in enumerate(ranked, start=1):
            fused[tool] = fused.get(tool, 0.0) + 1.0 / (rrf_k0 + rank)
    ranked = _rank(fused, k)
    return BaselineResult(
        "rag_mcp", "completed", [tool for tool, _ in ranked], _tool_ranking(ranked),
        details={"adapter": "global prompt + goal-view dense retrieval with RRF",
                 "query_views": len(queries), "rrf_k0": rrf_k0,
                 "no_structural_or_provenance_filter": True,
                 "clean_room_adaptation": True},
    )

def _colt_scene_completeness(
    retriever: HybridRetriever, query: str, pool: Sequence[str], k: int,
    training_scenes: Sequence[Mapping[str, Any]] | None,
    scene_weight: float = 0.5,
) -> BaselineResult:
    """Clean-room scene co-use adaptation; it is not the original trained COLT model."""
    scenes = list(training_scenes or [])
    if not scenes:
        return BaselineResult("colt_adapted", "blocked_missing_training_scenes",
                              details={"required": "training split query-to-tool bundles",
                                       "gold_leakage_guard": "no scene built from evaluation split"})
    if any(str(scene.get("split", "")).lower() not in {"train", "training"} for scene in scenes):
        raise ValueError("COLT-style scene index accepts training scenes only")
    visible = set(pool)
    pair_counts: Counter[tuple[str, str]] = Counter()
    tool_counts: Counter[str] = Counter()
    accepted_scenes = 0
    for scene in scenes:
        members = sorted(set(str(t) for t in scene.get("tools", [])) & visible)
        if not members:
            continue
        accepted_scenes += 1
        tool_counts.update(members)
        for i, left in enumerate(members):
            for right in members[i + 1:]:
                pair_counts[(left, right)] += 1
                pair_counts[(right, left)] += 1
    dense = retriever.scores(query, None, pool, set(), components=("den",))
    semantic = _minmax(dense)
    seed = [t for t, _ in _rank(dense, min(max(k, 3), max(1, len(pool))))]
    max_pair = max(pair_counts.values(), default=1)
    ranked_scores = {}
    for tool in pool:
        scene_support = max((pair_counts[(tool, seed_tool)] / max_pair
                             for seed_tool in seed if seed_tool != tool), default=0.0)
        ranked_scores[tool] = ((1.0 - scene_weight) * semantic.get(tool, 0.0)
                               + scene_weight * scene_support)
    ranked = _rank(ranked_scores, k)
    return BaselineResult("colt_adapted", "completed", [t for t, _ in ranked],
                          _tool_ranking(ranked),
                          details={"adapter": "scene-co-use clean-room approximation",
                                   "training_scene_count": accepted_scenes,
                                   "scene_weight": scene_weight,
                                   "semantic_weight": 1.0 - scene_weight,
                                   "training_only": True,
                                   "not_exact_original_reproduction": True})


def _toolscope_merge(
    retriever: HybridRetriever, query: str, pool: Sequence[str], k: int,
    threshold: float = 0.82, max_candidates: int = 1000,
) -> BaselineResult:
    """Semantic clustering plus context representative selection; provider identities survive."""
    ids = [t for t in pool if t in retriever.pos]
    if len(ids) > max_candidates:
        return BaselineResult("toolscope_adapted", "blocked_candidate_limit",
                              details={"candidate_count": len(ids), "max_candidates": max_candidates})
    if not ids:
        return BaselineResult("toolscope_adapted", "completed")
    positions = [retriever.pos[t] for t in ids]
    vectors = retriever.vecs[positions]
    parent = list(range(len(ids)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # O(n^2) exact pair comparisons; capped above and reported.
    for i in range(len(ids)):
        sims = vectors[i + 1:] @ vectors[i]
        for offset in np.flatnonzero(sims >= threshold):
            union(i, i + 1 + int(offset))
    groups: dict[int, list[str]] = defaultdict(list)
    for i, tool in enumerate(ids):
        groups[find(i)].append(tool)

    qvec = retriever.encoder.encode([query])[0]
    sims = vectors @ qvec
    context_score = {tool: float(sims[i]) for i, tool in enumerate(ids)}
    selected_groups = []
    for members in groups.values():
        ordered = sorted(members, key=lambda t: (-context_score[t], t))
        selected_groups.append((ordered[0], ordered, context_score[ordered[0]]))
    selected_groups.sort(key=lambda item: (-item[2], item[0]))
    selected = selected_groups[:k]
    ranking = [(tool, score) for tool, _, score in selected]
    return BaselineResult("toolscope_adapted", "completed", [x[0] for x in selected],
                          _tool_ranking(ranking), merged_groups=[x[1] for x in selected],
                          details={"adapter": "thresholded embedding cluster + contextual representative",
                                   "threshold": threshold,
                                   "candidate_count": len(ids),
                                   "cluster_count": len(groups),
                                   "selected_cluster_count": len(selected),
                                   "provider_tool_ids_preserved": True,
                                   "false_equivalence_requires_independent_labeling": True,
                                   "not_exact_original_reproduction": True})


def _cmtf_frontier(
    retriever: HybridRetriever,
    spec: GoalSpec,
    pool: Sequence[str],
    k: int,
    policy: Policy | None,
    max_expansions: int = 50000,
    max_depth: int = 8,
) -> BaselineResult:
    """Typed-state BFS adaptation returning next-action frontiers and cumulative tool union.

    Semantic types are planner state predicates. Tool effects are action effects. Since
    MCPBench gold execution states are not inferred here, this remains a typed-contract
    adaptation of CMTF rather than an exact reproduction.
    """
    contracts = retriever.contracts
    available = [contracts[t] for t in pool if t in contracts]
    order = spec.order()
    if order is None:
        return BaselineResult("cmtf_adapted", "invalid_goal_dependency_graph")
    state_types: set[SemType] = set(spec.prompt_inputs)
    selected_union: list[str] = []
    all_frontiers: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    explored_total = 0
    allowed = policy.allowed if policy is not None else None

    for goal in order:
        target = goal.out
        required_effects = tuple(goal.eff_plus)
        if any(subtype(value, target) for value in state_types) and not required_effects:
            trace.append({"goal_id": goal.id, "chain": [], "already_available": True})
            state_types.add(goal.out)
            continue

        def is_goal(types: frozenset[SemType], effects: frozenset[Effect]) -> bool:
            type_ok = any(subtype(value, target) for value in types)
            effect_ok = not required_effects or within(required_effects, effects)
            return type_ok and effect_ok

        start_types = frozenset(state_types)
        start_effects: frozenset[Effect] = frozenset()
        queue = deque([(start_types, start_effects, tuple())])
        seen = {(start_types, start_effects, tuple())}
        found: tuple[str, ...] | None = None
        first_frontier: set[str] = set()
        while queue and explored_total < max_expansions:
            types_now, effects_now, chain = queue.popleft()
            if is_goal(types_now, effects_now):
                found = chain
                break
            if len(chain) >= max_depth:
                continue
            for contract in sorted(available, key=lambda c: c.tool):
                if contract.tool in chain:
                    continue
                if not all(any(subtype(value, required) for value in types_now)
                           for required in contract.tail):
                    continue
                if allowed is not None and not within(contract.eff, allowed):
                    continue
                if not chain:
                    first_frontier.add(contract.tool)
                next_types = frozenset(set(types_now) | {contract.head})
                next_effects = frozenset(set(effects_now) | set(contract.eff))
                next_chain = chain + (contract.tool,)
                key = (next_types, next_effects, next_chain)
                if key in seen:
                    continue
                seen.add(key)
                queue.append((next_types, next_effects, next_chain))
                explored_total += 1
                if explored_total >= max_expansions:
                    break
        ordered_frontier = sorted(first_frontier)
        all_frontiers.append({"goal_id": goal.id, "tool_ids": ordered_frontier})
        if found is None:
            trace.append({"goal_id": goal.id, "chain": None, "search_exhausted": not bool(queue)})
            return BaselineResult("cmtf_adapted", "incomplete_search",
                                  list(dict.fromkeys(selected_union)),
                                  stepwise_frontiers=all_frontiers,
                                  details={"goal_traces": trace, "expanded_states": explored_total,
                                           "max_expansions": max_expansions,
                                           "max_depth": max_depth,
                                           "cumulative_union_is_partial": True,
                                           "frontier_semantics": "all immediately applicable actions"})
        for tool in found:
            if tool not in selected_union:
                selected_union.append(tool)
            state_types.add(contracts[tool].head)
        state_types.add(goal.out)
        trace.append({"goal_id": goal.id, "chain": list(found), "already_available": False})

    # Score cumulative chain tools for deterministic display; retain the sequence in trace.
    scores = retriever.scores(" ".join(g.rendering() for g in spec.goals), None,
                              selected_union, set(), components=("den",)) if selected_union else {}
    ranking = _tool_ranking(_rank(scores, len(selected_union)))
    return BaselineResult("cmtf_adapted", "completed", selected_union, ranking,
                          stepwise_frontiers=all_frontiers,
                          details={"goal_traces": trace, "expanded_states": explored_total,
                                   "frontier_semantics": "all immediately applicable actions",
                                   "cumulative_union_reported": True,
                                   "contract_model": "TaaS semantic input/output types + effects",
                                   "not_exact_original_reproduction": True})


def _autotool_trajectory(
    retriever: HybridRetriever, query: str, pool: Sequence[str], k: int,
    trajectories: Sequence[Mapping[str, Any]] | None,
    registry_hash: str | None, policy_hash: str | None,
    tool_hashes: Mapping[str, str] | None,
) -> BaselineResult:
    records = list(trajectories or [])
    if not records:
        return BaselineResult("autotool_adapted", "blocked_missing_confirmed_trajectories",
                              details={"trajectory_count": 0})
    if not registry_hash or not policy_hash or tool_hashes is None:
        return BaselineResult("autotool_adapted", "blocked_missing_revalidation_context",
                              details={"required": ["registry_hash", "policy_hash", "tool_hashes"]})
    records = [r for r in records if r.get("confirmed") is True
               and r.get("registry_hash") == registry_hash
               and r.get("policy_hash") == policy_hash
               and isinstance(r.get("query"), str)
               and isinstance(r.get("tool_ids"), list)]
    if not records:
        return BaselineResult("autotool_adapted", "blocked_no_current_confirmed_trajectory",
                              details={"revalidation": "no exact registry and policy match"})
    qvec = retriever.encoder.encode([query])[0]
    docs = [str(r["query"]) for r in records]
    vecs = retriever.encoder.encode(docs)
    sim = vecs @ qvec
    votes: dict[str, float] = defaultdict(float)
    accepted_records = 0
    for index in np.argsort(-sim):
        record = records[int(index)]
        hashes = record.get("tool_hashes", {})
        current_tools = []
        for tool in record["tool_ids"]:
            if tool in pool and isinstance(hashes, dict) and hashes.get(tool) == tool_hashes.get(tool):
                current_tools.append(tool)
        if not current_tools:
            continue
        accepted_records += 1
        weight = max(0.0, float(sim[int(index)]))
        for tool in current_tools:
            votes[tool] += weight
    ranked = _rank(votes, k)
    return BaselineResult("autotool_adapted", "completed" if ranked else "no_revalidated_tools",
                          [t for t, _ in ranked], _tool_ranking(ranked),
                          details={"confirmed_records_considered": len(records),
                                   "records_with_revalidated_tools": accepted_records,
                                   "registry_hash_matched": True,
                                   "policy_hash_matched": True,
                                   "tool_definition_hash_revalidated": True,
                                   "trajectory_reuse_is_not_execution": True})


def run_baseline(
    baseline_id: str,
    retriever: HybridRetriever,
    spec: GoalSpec,
    prompt: str,
    pool: Sequence[str],
    top_k: int = 5,
    policy: Policy | None = None,
    training_scenes: Sequence[Mapping[str, Any]] | None = None,
    trajectories: Sequence[Mapping[str, Any]] | None = None,
    registry_hash: str | None = None,
    policy_hash: str | None = None,
    tool_hashes: Mapping[str, str] | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> BaselineResult:
    """Run a registered discovery baseline without evaluator-label access."""
    index = baseline_index()
    if baseline_id not in index:
        raise KeyError(f"Unknown baseline id: {baseline_id}")
    spec_def = index[baseline_id]
    maturity = spec_def["implementation"]
    executable = {"ready", "ready_surrogate", "ready_adaptation", "partial_adapter", "core_method"}
    if maturity not in executable:
        return BaselineResult(baseline_id, "adapter_not_implemented",
                              details={"implementation_maturity": maturity,
                                       "reason": "This baseline requires a separate pipeline/runtime adapter."})
    explicit_params = dict(parameters or {})
    params = dict(spec_def.get("params", {}))
    params.update(explicit_params)
    requested_k = explicit_params.get("top_k", top_k if top_k is not None else params.get("top_k", 5))
    k = int(requested_k) if isinstance(requested_k, int) else 5
    visible = [t for t in pool if t in retriever.contracts]

    if baseline_id == "all_tools":
        selected = all_tools(visible)
        return BaselineResult(baseline_id, "completed", selected,
                              details={"control": "unfiltered full registry",
                                       "candidate_count": len(visible)})

    if baseline_id == "bm25":
        return _bm25(retriever, prompt, visible, k)
    if baseline_id == "dense_lsa":
        return _dense(retriever, prompt, visible, k, baseline_id)
    if baseline_id == "rag_mcp":
        return _rag_multiquery(retriever, prompt, spec, visible, k, int(params.get("rrf_k0", 60)))

    if baseline_id == "mcp_zero":
        selected = mcp_zero(retriever, spec, visible,
                            servers_k=int(params.get("top_servers", 1)))
        scores = retriever.scores(prompt, None, selected, set(), components=("den",)) if selected else {}
        return BaselineResult(baseline_id, "completed", selected, _tool_ranking(_rank(scores, len(selected))),
                              details={"adapter": "single-pass hierarchical server routing",
                                       "active_request_loop": False,
                                       "top_servers": int(params.get("top_servers", 1)),
                                       "exact_original_reproduction": False})

    if baseline_id == "per_subtask":
        selected = per_subtask(retriever, spec, visible,
                               k_per_goal=int(params.get("k_per_goal", 1)),
                               include_native=bool(params.get("include_native", True)))
        scores = retriever.scores(prompt, None, selected, set(), components=("den",)) if selected else {}
        return BaselineResult(baseline_id, "completed", selected, _tool_ranking(_rank(scores, len(selected))),
                              details={"union_of_independent_goal_shortlists": True,
                                       "joint_validation": False})

    if baseline_id == "colt_adapted":
        return _colt_scene_completeness(
            retriever, prompt, visible, k, training_scenes,
            float(params.get("scene_weight", 0.5)))

    if baseline_id == "toolscope_adapted":
        return _toolscope_merge(retriever, prompt, visible, k,
                                float(params.get("merge_threshold", 0.82)),
                                int(params.get("max_merge_candidates", 1000)))

    if baseline_id == "cmtf_adapted":
        return _cmtf_frontier(retriever, spec, visible, k, policy,
                              int(params.get("max_expansions", 50000)),
                              int(params.get("max_depth", 8)))

    if baseline_id == "autotool_adapted":
        return _autotool_trajectory(retriever, prompt, visible, k, trajectories,
                                    registry_hash, policy_hash, tool_hashes)

    return BaselineResult(baseline_id, "adapter_not_implemented",
                          details={"implementation_maturity": maturity})
