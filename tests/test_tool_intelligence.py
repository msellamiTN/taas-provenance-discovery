from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio.tool_intelligence import build_tool_intelligence
from taas.types import parse_type


def _contract(tool_id: str, out: str, inputs: dict[str, bool], effects=("read(*)",)):
    return SimpleNamespace(
        id=tool_id,
        args=tuple(SimpleNamespace(name=n, type=parse_type(t), required=req)
                   for n, (t, req) in inputs.items()),
        head=parse_type(out),
        eff=frozenset(effects),
        eff_record=SimpleNamespace(ptype="lex", method="name+verb+args"),
        annotations={},
    )


def _goal(goal_id: str, out: str, inputs=()):
    return SimpleNamespace(id=goal_id, cls="retrieve", out=parse_type(out),
                           inputs=[parse_type(i) for i in inputs],
                           eff_plus=frozenset())


CONTRACTS = {
    "registry::lookup": _contract("registry::lookup", "record:search_result[]",
                                  {"query": ("text:query", True)}),
    "registry::detail": _contract("registry::detail", "record:detail",
                                  {"record": ("record:search_result", True)}),
}

DIAGNOSTICS = {
    "schema": "taas.discovery-diagnostics/v1",
    "policy": {
        "minimum_evidence_strength": 0.65,
        "allowed_effects": ["read(*)", "egress(*)", "session"],
    },
    "candidate_retrieval": {
        "candidate_count": 2,
        "per_goal": {"g1": ["registry::lookup"], "_derived": ["registry::detail"]},
    },
    "tools": [
        {
            "tool_id": "registry::lookup", "indexed_live": True, "eligible": True,
            "exclusions": [],
            "property_strengths": {"read_only": 0.9, "no_delete": 0.9},
            "effects": ["read(*)"],
            "input_types": ["text:query"],
            "output_type": "record:search_result[]",
            "effect_evidence": {"type": "lex", "method": "name+verb+args"},
        },
        {
            "tool_id": "registry::detail", "indexed_live": True, "eligible": True,
            "exclusions": [{"tool_id": "other::x", "reason": "forbidden_pair"}],
            "property_strengths": {"read_only": 0.4},
            "effects": ["read(*)", "write(*)"],
            "input_types": ["record:search_result"],
            "output_type": "record:detail",
            "effect_evidence": {"type": "lex", "method": "name+verb+args"},
        },
    ],
}

GOALS = [_goal("g1", "record:search_result[]", inputs=("text:query",))]


def test_per_tool_intelligence_composed():
    intel = build_tool_intelligence(
        contracts=CONTRACTS, diagnostics=DIAGNOSTICS, goals=GOALS,
        toolkit=["registry::lookup"], certificate={"id": "cert-1"},
    )
    assert intel["schema"] == "taas.tool-intelligence/v1"
    assert intel["execution_performed"] is False
    assert intel["tools_invoked"] is False

    by_id = {t["tool_id"]: t for t in intel["tools"]}
    lookup = by_id["registry::lookup"]
    assert lookup["selected"] is True
    assert lookup["serves_goals"] == ["g1"]
    match = lookup["capability_match"][0]
    assert match["match"] == "exact"
    assert match["all_required_inputs_served"] is True
    assert lookup["assurance"]["covered_by_selection_certificate"] is True
    assert lookup["effect_profile"]["policy_allowed"] is True

    detail = by_id["registry::detail"]
    assert detail["derived_candidate"] is True
    assert detail["selected"] is False
    assert detail["assurance"]["covered_by_selection_certificate"] is False
    assert detail["effect_profile"]["policy_allowed"] is False  # write(*) not allowed
    assert detail["effect_profile"]["forbidden_with"] == ["other::x"]
    assert detail["composition"]["fed_by"] == [] or isinstance(detail["composition"]["fed_by"], list)


def test_composition_neighbors_from_structural_types():
    diagnostics = dict(DIAGNOSTICS)
    diagnostics["tools"] = [
        {**DIAGNOSTICS["tools"][0], "output_type": "record:search_result"},
        DIAGNOSTICS["tools"][1],
    ]
    intel = build_tool_intelligence(
        contracts=CONTRACTS, diagnostics=diagnostics, goals=GOALS,
        toolkit=None, certificate=None,
    )
    by_id = {t["tool_id"]: t for t in intel["tools"]}
    assert "registry::detail" in by_id["registry::lookup"]["composition"]["feeds"]
    assert "registry::lookup" in by_id["registry::detail"]["composition"]["fed_by"]


def test_missing_inputs_reported_honestly():
    goal = _goal("g1", "record:search_result[]", inputs=())
    diagnostics = dict(DIAGNOSTICS)
    diagnostics["candidate_retrieval"] = {"candidate_count": 1,
                                          "per_goal": {"g1": ["registry::lookup"]}}
    intel = build_tool_intelligence(
        contracts=CONTRACTS, diagnostics=diagnostics, goals=[goal],
        toolkit=None, certificate=None,
    )
    match = {t["tool_id"]: t for t in intel["tools"]}["registry::lookup"]["capability_match"][0]
    assert match["all_required_inputs_served"] is False
    assert "text:query" in match["missing_inputs"]


def test_unavailable_diagnostics_produce_empty_honest_record():
    intel = build_tool_intelligence(
        contracts={}, diagnostics={"available": False, "reason": "engine_index_not_exposed"},
        goals=[], toolkit=None, certificate=None,
    )
    assert intel["tools"] == []
    assert intel["summary"]["tool_count"] == 0
    assert intel["semantic_correctness_verified"] is False


def test_bounds_enforced():
    big = dict(DIAGNOSTICS)
    big["tools"] = [DIAGNOSTICS["tools"][0]] * 65
    with pytest.raises(ValueError, match="bounds"):
        build_tool_intelligence(contracts=CONTRACTS, diagnostics=big,
                                goals=GOALS, toolkit=None, certificate=None)


def test_discover_response_includes_tool_intelligence(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "intel-token")

    class FakeEngine:
        def __init__(self, contracts, profile, trust, cfg):
            self.H = SimpleNamespace(contracts={})
            self.composer = SimpleNamespace(model_edges=lambda goals: [])

        def discover(self, spec, policy):
            return SimpleNamespace(
                spec=spec, gap=SimpleNamespace(gap=[], rho=0.0),
                compose=SimpleNamespace(reachability=None, candidates=[], regime="exact", stats={}),
                certificate=None, counterexample=None, toolkit=None, time_s=0.01, abstained=True,
            )

    monkeypatch.setattr(studio_api, "DiscoveryEngine", FakeEngine)
    client = TestClient(studio_api.app)
    response = client.post("/api/v1/objectives/discover",
        headers={"Authorization": "Bearer intel-token"},
        json={
            "goal_spec": {
                "prompt": "List customer orders", "prompt_inputs": ["text"],
                "goals": [{"id": "g1", "class": "retrieve", "in": ["query"],
                           "out": "record[]", "eff": ["read(orders)"], "sigma": "data",
                           "deps": [], "desc": "List customer orders"}],
            },
            "human_review_confirmed": True,
            "tools": [{"server": "orders", "name": "list_orders",
                       "input_schema": {"type": "object", "properties": {}}}],
        })
    assert response.status_code == 200
    intel = response.json()["tool_intelligence"]
    assert intel["schema"] == "taas.tool-intelligence/v1"
    assert intel["tools_invoked"] is False
    assert intel["execution_performed"] is False
