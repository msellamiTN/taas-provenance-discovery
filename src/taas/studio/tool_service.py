"""Tool Intelligence v1.2 — explainable hybrid retrieval over the registry.

Reuses the retained-registry DiscoveryEngine container for its fitted index and
retriever, then exposes what ``HybridRetriever.scores()`` computes internally:
per-component (lexical BM25, dense cosine, structural type) raw score, rank and
RRF contribution per tool. Relevance scores are retrieval relevance only —
never capability, evidence trust, eligibility or authorization claims.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

from taas.composer import eligible_set
from taas.contracts import extract_contract
from taas.engine import DiscoveryEngine
from taas.model_profile import ModelProfile
from taas.provenance import EvidenceStore, ProvenanceRecord
from taas.retrieval import structural_score
from taas.studio import tool_registry
from taas.types import SemType, parse_type, subtype

RETRIEVAL_SCHEMA = "taas.retrieval-explanation/v1"
_COMPONENTS = ("lex", "den", "str")

EVIDENCE_STORE_ENV = "TAAS_EVIDENCE_STORE"


def load_evidence_store(path: str | Path) -> EvidenceStore:
    """Load obs/att provenance records from a JSONL file.

    One JSON object per line::

        {"tool": "server::name", "definition_hash": "<h>",
         "prop": "read_only", "ptype": "obs"|"att",
         "signer": "...", "kappa": 0.0-1.0, "method": "...",
         "effects": ["read(fs)"]}

    ``prop`` lines append a provenance record for ``(tool, h)``; ``effects``
    sets the observed-effect list for that pair. Malformed lines are skipped —
    never silently fabricated. Stale definition hashes simply never match at
    contract-extraction time.
    """
    store = EvidenceStore()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        tool, h = rec.get("tool"), rec.get("definition_hash")
        if not isinstance(tool, str) or not isinstance(h, str):
            continue
        if isinstance(rec.get("effects"), list):
            store.set_observed_effects(tool, h, [str(e) for e in rec["effects"]])
        prop = rec.get("prop")
        if not isinstance(prop, str):
            continue
        try:
            store.add(tool, h, prop, ProvenanceRecord(
                ptype=rec.get("ptype", "obs"),
                signer=rec.get("signer"),
                kappa=float(rec.get("kappa", 1.0)),
                method=str(rec.get("method", "external")),
            ))
        except ValueError:
            continue
    return store


@lru_cache(maxsize=1)
def _evidence_store() -> EvidenceStore | None:
    """Shared obs/att evidence store when TAAS_EVIDENCE_STORE points at a file."""
    path = os.environ.get(EVIDENCE_STORE_ENV)
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return load_evidence_store(p)
    except OSError:
        return None


def configured_evidence_store() -> EvidenceStore | None:
    """Public accessor for API surfaces that wire the shared store."""
    return _evidence_store()


@lru_cache(maxsize=1)
def _tool_engine() -> DiscoveryEngine:
    """Fitted Core engine over the retained registry; shared, read-only."""
    store = _evidence_store()
    contracts = [extract_contract(raw, store=store) for raw in tool_registry._raw_tools().values()]
    return DiscoveryEngine(contracts, ModelProfile(model_id="registry-service", strict=True))


def reset_tool_service_caches() -> None:
    _tool_engine.cache_clear()
    _evidence_store.cache_clear()


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
        "evidence_store_wired": _evidence_store() is not None,
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
        "evidence_store_wired": _evidence_store() is not None,
        "execution_performed": False,
        "semantic_correctness_verified": False,
    }


COMPARE_SCHEMA = "taas.tool-compare/v1"


def compare_tools(
    tool_ids: Sequence[str],
    *,
    policy: Any = None,
    query: str | None = None,
    goal_out: SemType | str | None = None,
    evidence_store: Any = None,
    attestation_lookup: Any = None,
) -> dict[str, Any]:
    """Deterministic side-by-side comparison of exact registry tools.

    Capability rows reuse ``build_capability_profile``; evidence strengths come
    from the shared index; eligibility verdicts reuse the ``eligible_set``
    semantics; optional retrieval scores reuse the same per-component math as
    ``explainable_retrieve`` restricted to the compared ids. Comparison is
    structural — never a relevance/capability/authorization verdict by itself.
    """
    engine = _tool_engine()
    index = engine.index
    live = set(index.to_ids(index.live))
    known = sorted(t for t in tool_ids if t in live)
    unknown = sorted(t for t in tool_ids if t not in live)

    capability_rows: dict[str, Any] = {}
    for tool_id in known:
        server, name = tool_id.split("::", 1)
        profile = tool_registry.build_capability_profile(
            server, name, evidence_store=evidence_store,
            attestation_lookup=attestation_lookup,
        )
        capability_rows[tool_id] = profile

    diff_fields: dict[str, dict[str, Any]] = {}
    def _collect(field: str, values: dict[str, Any]) -> None:
        distinct = {str(v) for v in values.values()}
        if len(distinct) > 1:
            diff_fields[field] = values

    _collect("tool_class", {t: capability_rows[t]["capability"]["tool_class"] for t in capability_rows})
    _collect("output_type", {t: capability_rows[t]["capability"]["output_type"] for t in capability_rows})
    _collect("evidence_kind", {t: capability_rows[t]["effects"]["evidence_kind"] for t in capability_rows})
    _collect("declared_effects", {
        t: sorted(capability_rows[t]["effects"]["declared_effects"]) for t in capability_rows})
    _collect("required_credentials", {
        t: sorted(capability_rows[t]["capability"]["required_credentials"]) for t in capability_rows})

    strengths = {t: index.strengths.get(t, {}) for t in known}

    eligibility: dict[str, Any] | None = None
    if policy is not None:
        eligible_ids = set(eligible_set(index, policy))
        eligibility = {
            t: {"eligible": t in eligible_ids}
            for t in known
        }
        for t in known:
            sub = eligibility_explain(policy, [t])
            eligibility[t]["rejection_reasons"] = sub["tools"][0]["rejection_reasons"] if sub["tools"] else []

    retrieval: dict[str, Any] | None = None
    if query is not None:
        out_type = parse_type(goal_out) if goal_out else None
        reach = engine.H.reach([], [], [], engine.profile)
        comp_scores = _per_component_scores(
            engine.retriever, query, out_type, known, reach.types, _COMPONENTS)
        tables = _rrf_tables(comp_scores, engine.retriever.k0)
        fused = {t: sum(tbl.get(t, {}).get("rrf_contribution", 0.0) for tbl in tables.values())
                 for t in known}
        retrieval = {
            "query": query,
            "goal_out": str(out_type) if out_type else None,
            "scores": {
                t: {
                    "fused": fused[t],
                    "components": {
                        name: tbl.get(t, {"score": 0.0, "rank": None, "rrf_contribution": 0.0})
                        for name, tbl in tables.items()
                    },
                }
                for t in known
            },
        }

    return {
        "schema": COMPARE_SCHEMA,
        "tools": {
            t: {
                "capability": capability_rows[t]["capability"] if t in capability_rows else None,
                "effects": capability_rows[t]["effects"] if t in capability_rows else None,
                "evidence_summary": capability_rows[t]["evidence_summary"] if t in capability_rows else None,
                "property_strengths": strengths.get(t, {}),
                "definition_hash_verified": (
                    capability_rows[t]["identity"].get("definition_hash_verified")
                    if t in capability_rows else None
                ),
            }
            for t in known
        },
        "differences": diff_fields,
        "eligibility": eligibility,
        "retrieval": retrieval,
        "unknown_tool_ids": unknown,
        "summary": {"compared": len(known), "unknown": len(unknown),
                    "differing_fields": sorted(diff_fields)},
        "comparison_semantics": "structural_capability_evidence_eligibility_diff_only_not_authorization",
        "evidence_store_wired": evidence_store is not None,
        "execution_performed": False,
        "semantic_correctness_verified": False,
    }
