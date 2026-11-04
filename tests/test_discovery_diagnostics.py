from types import SimpleNamespace

from taas.bitmap_index import BitmapIndex
from taas.contracts import make_contract
from taas.engine import DiscoveryEngine
from taas.model_profile import ModelProfile
from taas.policy import Policy
from taas.studio.discovery_diagnostics import build_discovery_diagnostics


def _engine_with_contract(contract):
    index = BitmapIndex()
    index.insert(contract)
    graph = SimpleNamespace(contracts={contract.tool: contract})
    return SimpleNamespace(index=index, H=graph)


def test_empty_positive_policy_reports_live_contract_as_eligible():
    contract = make_contract(
        "catalog::lookup",
        {"query": "query"},
        "record[]",
        ["read(catalog)"],
        evidence="obs",
        description="Look up records by query",
    )
    engine = _engine_with_contract(contract)
    policy = Policy.make("default")

    result = build_discovery_diagnostics(
        engine, policy, {"eligible": 1, "candidates": 0, "per_goal": {"g1": []}},
        toolkit=None, abstained=True,
    )

    assert result["available"] is True
    assert result["index_live_count"] == 1
    assert result["eligibility"]["eligible_tool_ids"] == [contract.tool]
    assert result["eligibility"]["composition_count_matches_preflight"] is True
    assert result["pipeline_stage"] == "candidate_retrieval_or_type_matching"
    assert result["execution_performed"] is False
    assert result["semantic_correctness_verified"] is False


def test_positive_policy_exclusion_explains_missing_required_evidence():
    contract = make_contract(
        "catalog::lookup",
        {"query": "query"},
        "record[]",
        ["read(catalog)"],
        evidence="lex",
        description="Look up records by query",
    )
    engine = _engine_with_contract(contract)
    policy = Policy.make("requires-attestation", required={"read_only"}, lmin="obs")

    result = build_discovery_diagnostics(engine, policy, {"eligible": 0, "candidates": 0}, None, True)

    assert result["eligibility"]["eligible_count"] == 0
    tool = result["tools"][0]
    assert tool["eligible"] is False
    assert tool["exclusions"] == [{
        "stage": "positive_policy",
        "property": "read_only",
        "strength": tool["property_strengths"]["read_only"],
        "required_strength": policy.lmin,
    }]


def test_closed_world_policy_exclusion_explains_forbidden_evidence():
    contract = make_contract(
        "ops::update_record",
        {"record": "record[]"},
        "record[]",
        ["write(db)"],
        evidence="obs",
        description="Update a record",
    )
    engine = _engine_with_contract(contract)
    policy = Policy.make(
        "no-writes",
        forbidden={"writes"},
        encoding="closed_world",
        lmin="obs",
    )

    result = build_discovery_diagnostics(engine, policy, {"eligible": 0, "candidates": 0}, None, True)

    assert result["eligibility"]["eligible_count"] == 0
    assert result["tools"][0]["exclusions"][0]["stage"] == "closed_world_policy"
    assert result["pipeline_stage"] == "policy_eligibility"


def test_diagnostics_explicitly_report_missing_engine_index():
    result = build_discovery_diagnostics(SimpleNamespace(), Policy.make("default"))
    assert result == {
        "schema": "taas.discovery-diagnostics/v1",
        "available": False,
        "reason": "engine_index_not_exposed",
    }
