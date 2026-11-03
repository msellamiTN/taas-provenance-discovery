from taas.contracts import make_contract
from taas.hypergraph import Derivation, Hypergraph, ModelEdge, ReachResult
from taas.hypergraph_projection import PROJECTION_SCHEMA, project_hypergraph
from taas.types import parse_type


def _graph():
    graph = Hypergraph()
    contract = make_contract(
        "orders::list_orders",
        {"customer_id": "identifier", "limit": "number"},
        "record:order[]",
        ["read(orders)"],
        optional=("limit",),
        description="List orders for a customer",
        source_label="internal",
    )
    graph.add(contract)
    return graph, contract


def test_projection_uses_core_contract_and_reachability_without_recomputing():
    graph, contract = _graph()
    reach = ReachResult(
        types={parse_type("identifier"), parse_type("record:order[]")},
        derivations={
            "identifier": Derivation("prompt", "identifier", (), "prompt"),
            "record:order[]": Derivation(
                contract.tool, "record:order[]", ("identifier",), "tool", 0.95
            ),
        },
        bridges=[],
        labels={"identifier": "public", "record:order[]": "internal"},
        fired={contract.tool},
        tool_types={"record:order[]": contract.tool},
    )

    result = project_hypergraph(graph, reach)
    assert result["schema"] == PROJECTION_SCHEMA
    assert result["summary"]["registered_tool_count"] == 1
    assert result["summary"]["reachable_type_count"] == 2

    edge = next(item for item in result["hyperedges"] if item["kind"] == "tool")
    assert edge["tool_id"] == contract.tool
    assert edge["required_inputs"] == ["identifier"]
    assert {item["argument"] for item in edge["tail"]} == {"customer_id", "limit"}
    assert edge["head"] == "record:order[]"
    assert edge["effects"] == ["read(orders)"]
    assert edge["information_source_label"] == "internal"
    assert edge["fired_in_reachability"] is True

    nodes = {item["semantic_type"]: item for item in result["vertices"]}
    assert nodes["record:order[]"]["reachable"] is True
    assert nodes["record:order[]"]["information_label"] == "internal"
    assert nodes["record:order[]"]["derivation"]["edge_id"] == contract.tool


def test_projection_keeps_unreachable_contract_types_visible():
    graph, contract = _graph()
    reach = ReachResult(
        types={parse_type("identifier")},
        derivations={"identifier": Derivation("prompt", "identifier", (), "prompt")},
        bridges=[],
        labels={"identifier": "public"},
    )
    result = project_hypergraph(graph, reach)
    nodes = {item["semantic_type"]: item for item in result["vertices"]}
    assert nodes["record:order[]"]["reachable"] is False
    assert nodes["record:order[]"]["information_label"] is None


def test_projection_rejects_unknown_tool_ids():
    graph, _ = _graph()
    reach = ReachResult(set(), {}, [])
    try:
        project_hypergraph(graph, reach, selected_tools=["unknown::tool"])
    except ValueError as exc:
        assert "unknown::tool" in str(exc)
    else:
        raise AssertionError("unknown tool identifier must be rejected")


def test_projection_includes_model_edges_and_bridges():
    graph, _ = _graph()
    model = ModelEdge(
        cls="summarise",
        tail=(parse_type("record:order[]"),),
        head=parse_type("text"),
        rho=0.82,
        goal="g-summary",
    )
    reach = ReachResult(
        types={parse_type("record:order[]"), parse_type("text")},
        derivations={"text": Derivation(model.id, "text", ("record:order[]",), "model", 0.82)},
        bridges=[Derivation("LLM::extract", "identifier", ("text",), "bridge", 0.75)],
        labels={"record:order[]": "internal", "text": "internal"},
        fired={model.id},
    )
    result = project_hypergraph(graph, reach, selected_tools=[], model_edges=[model])
    assert any(edge["kind"] == "model" and edge["goal_id"] == "g-summary"
               for edge in result["hyperedges"])
    assert len(result["bridges"]) == 1
    assert result["bridges"][0]["operation"] == "LLM::extract"
