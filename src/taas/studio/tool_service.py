"""Tool Intelligence v1.2 — explainable hybrid retrieval over the registry.

Reuses the retained-registry DiscoveryEngine container for its fitted index and
retriever, then exposes what ``HybridRetriever.scores()`` computes internally:
per-component (lexical BM25, dense cosine, structural type) raw score, rank and
RRF contribution per tool. Relevance scores are retrieval relevance only —
never capability, evidence trust, eligibility or authorization claims.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable, Sequence

from taas.composer import eligible_set
from taas.contracts import extract_contract
from taas.engine import DiscoveryEngine
from taas.model_profile import ModelProfile
from taas.retrieval import structural_score
from taas.studio import tool_registry
from taas.types import SemType, parse_type, subtype

RETRIEVAL_SCHEMA = "taas.retrieval-explanation/v1"
_COMPONENTS = ("lex", "den", "str")


@lru_cache(maxsize=1)
def _tool_engine() -> DiscoveryEngine:
    """Fitted Core engine over the retained registry; shared, read-only."""
    contracts = [extract_contract(raw) for raw in tool_registry._raw_tools().values()]
    return DiscoveryEngine(contracts, ModelProfile(model_id="registry-service", strict=True))


def reset_tool_service_caches() -> None:
    _tool_engine.cache_clear()


def _per_component_scores(
    retriever: Any,
    query: str,
    goal_out: SemType | None,
    eligible: Sequence[str],
    reach_types: set[SemType],
    components: Sequence[str],
) -> dict[str, dict[str, float]]:
    """Replicate ``HybridRetriever.scores`` per-component rankings read-only."""
    ret = retriever
    elig = [t for t in eligible if t in ret.pos]
    idx = [ret.pos[t] for t in elig]
    component_scores: dict[str, dict[str, float]] = {}
    if "lex" in components:
        raw = ret.bm25.scores(query, idx)
        component_scores["lex"] = {ret.ids[i]: v for i, v in raw.items()}
    if "den" in components:
        q = ret.encoder.encode([query])[0]
        sims = ret.vecs[idx] @ q
        component_scores["den"] = {t: float(v) for t, v in zip(elig, sims)}
    if "str" in components and goal_out is not None:
        component_scores["str"] = {
            t: structural_score(
                ret.contracts[t].head, ret.contracts[t].out.confidence,
                ret.contracts[t].tail, goal_out, reach_types, ret.kappa_min,
            )
            for t in elig
        }
    return component_scores


def _rrf_tables(component_scores: dict[str, dict[str, float]], k0: int) -> dict[str, dict[str, dict[str, float]]]:
    """Rank per component (score desc, id tiebreak) and RRF contribution — mirrors scores()."""
    tables: dict[str, dict[str, dict[str, float]]] = {}
    single = len(component_scores) == 1
    for name, scores in component_scores.items():
        order = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        table: dict[str, dict[str, float]] = {}
        for rank, (tool_id, score) in enumerate(order, start=1):
            table[tool_id] = {
                "score": score,
                "rank": rank,
                "rrf_contribution": 1.0 / (k0 + rank) if score > 0 or single else 0.0,
            }
        tables[name] = table
    return tables


def explainable_retrieve(
    query: str,
    goal_out: SemType | str | None,
    *,
    policy: Any,
    k: int = 10,
    components: Sequence[str] | None = None,
    type_filter: bool = True,
    prompt_inputs: Iterable[str] = (),
    include_hypergraph: bool = False,
) -> dict[str, Any]:
    """Top-K eligible tools with per-component score/rank/contribution explanation."""
    engine = _tool_engine()
    retriever = engine.retriever
    comps = tuple(components or _COMPONENTS)
    unknown = [c for c in comps if c not in _COMPONENTS]
    if unknown:
        raise ValueError(f"Unknown retrieval components: {', '.join(unknown)}")
    out_type = parse_type(goal_out) if goal_out else None
    eligible = eligible_set(engine.index, policy)
    reach = engine.H.reach([], [parse_type(x) for x in prompt_inputs], [], engine.profile)
    component_scores = _per_component_scores(retriever, query, out_type, eligible, reach.types, comps)
    tables = _rrf_tables(component_scores, retriever.k0)

    fused: dict[str, float] = {t: 0.0 for t in eligible if t in retriever.pos}
    for table in tables.values():
        for tool_id, cell in table.items():
            fused[tool_id] += cell["rrf_contribution"]

    def serves(tool_id: str) -> bool:
        if out_type is None:
            return True
        contract = retriever.contracts[tool_id]
        return subtype(contract.head, out_type) and contract.out.confidence >= retriever.kappa_min

    ranked = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
    results = []
    for tool_id, score in ranked:
        passes = serves(tool_id)
        if type_filter and out_type is not None and not passes:
            continue
        results.append({
            "tool_id": tool_id,
            "rrf_score": score,
            "type_filter_pass": passes,
            "components": {
                name: table.get(tool_id, {"score": 0.0, "rank": None, "rrf_contribution": 0.0})
                for name, table in tables.items()
            },
        })
        if len(results) >= k:
            break

    body: dict[str, Any] = {
        "schema": RETRIEVAL_SCHEMA,
        "query": query,
        "goal_out": str(out_type) if out_type else None,
        "k": k,
        "components_used": sorted(tables),
        "k0": retriever.k0,
        "kappa_min": retriever.kappa_min,
        "eligible_count": len(eligible),
        "results": results,
        "score_semantics": "retrieval_relevance_only_not_capability_evidence_eligibility_or_authorization",
        "execution_performed": False,
        "semantic_correctness_verified": False,
    }
    if include_hypergraph:
        from taas.hypergraph_projection import project_hypergraph
        top_ids = [item["tool_id"] for item in results]
        body["hypergraph_projection"] = project_hypergraph(
            engine.H, reach, selected_tools=top_ids or (),
        )
    return body


ELIGIBILITY_SCHEMA = "taas.eligibility-explanation/v1"


def eligibility_explain(policy: Any, tool_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Explain per-tool policy eligibility mirroring ``eligible_set`` exactly.

    Positive encoding: every required property must reach ``lmin`` strength.
    Closed-world encoding: no forbidden property may reach ``lmin``. Visibility
    restricts the universe in both modes. Strengths come from the index — they
    are evidence-strength scores, never relevance or authorization.
    """
    engine = _tool_engine()
    index = engine.index
    live_ids = index.to_ids(index.live)
    eligible_ids = set(eligible_set(index, policy))
    strengths = index.strengths

    requested = list(tool_ids) if tool_ids is not None else live_ids
    unknown = sorted(t for t in requested if t not in set(live_ids))
    lmin = policy.lmin
    try:
        lmin_value = float(lmin)
    except (TypeError, ValueError):
        lmin_value = lmin

    tools = []
    for tool_id in sorted(t for t in requested if t in set(live_ids)):
        tool_strengths = strengths.get(tool_id, {})
        visible = policy.visible is None or tool_id in policy.visible
        reasons = []
        detail: dict[str, Any] = {"visible": visible}
        if not visible:
            reasons.append("not_in_policy_visible_set")
        if policy.encoding == "positive":
            props = {
                prop: {
                    "strength": tool_strengths.get(prop, 0.0),
                    "required": lmin_value,
                    "met": tool_strengths.get(prop, 0.0) >= lmin_value,
                }
                for prop in sorted(policy.required)
            }
            detail["required_properties"] = props
            reasons += [f"required_property_below_strength:{p}" for p, v in props.items() if not v["met"]]
        else:
            props = {
                prop: {
                    "strength": tool_strengths.get(prop, 0.0),
                    "forbidden_at": lmin_value,
                    "violated": tool_strengths.get(prop, 0.0) >= lmin_value,
                }
                for prop in sorted(policy.forbidden)
            }
            detail["forbidden_properties"] = props
            reasons += [f"forbidden_property_at_strength:{p}" for p, v in props.items() if v["violated"]]
        tools.append({
            "tool_id": tool_id,
            "eligible": tool_id in eligible_ids,
            "rejection_reasons": reasons,
            **detail,
        })

    return {
        "schema": ELIGIBILITY_SCHEMA,
        "policy": {
            "encoding": policy.encoding,
            "required_properties": sorted(policy.required),
            "forbidden_properties": sorted(policy.forbidden),
            "minimum_evidence_strength": lmin,
            "visible_tool_count": len(policy.visible) if policy.visible is not None else None,
        },
        "eligible_ids": sorted(eligible_ids),
        "tools": tools,
        "unknown_tool_ids": unknown,
        "summary": {
            "evaluated": len(tools),
            "eligible": sum(1 for t in tools if t["eligible"]),
            "rejected": sum(1 for t in tools if not t["eligible"]),
            "unknown": len(unknown),
        },
        "eligibility_semantics": "policy_evidence_strength_only_not_relevance_capability_or_authorization",
        "execution_performed": False,
        "semantic_correctness_verified": False,
    }
