from taas.certificate import Certificate
from taas.contracts import make_contract
from taas.effects import parse_effects
from taas.experiments.independent_certificate_audit import audit_certificate
from taas.goals import GoalContract
from taas.hypergraph import Hypergraph
from taas.policy import Policy
from taas.types import parse_type


def fixture():
    contract = make_contract(
        "reporter::build_report", {"source": "text"}, "record(report)",
        ["read(*)"], evidence="obs",
    )
    graph = Hypergraph()
    graph.add(contract)
    goal = GoalContract(
        id="g1", cls="answer", inputs=[parse_type("text")],
        out=parse_type("record(report)"), sigma="data",
    )
    policy = Policy.make("test", allowed=["read(*)"])
    certificate = Certificate(
        toolkit=[contract.tool],
        checks={key: True for key in ("S", "C", "P", "E", "L", "V", "M", "B")},
        witnesses={}, regime="test", cost=0.0, util=1.0,
        bridge_ratio=0.0, bindings={"g1": contract.tool},
    )
    return certificate, graph, goal, policy


def test_independent_audit_accepts_matching_recomputed_mandatory_checks():
    certificate, graph, goal, policy = fixture()
    result = audit_certificate(
        certificate, graph, [goal], [parse_type("text")], policy,
    )
    assert result.valid is True
    assert set(result.recomputed) == {"S", "C", "P", "E", "L", "V"}
    assert all(result.matches.values())


def test_independent_audit_detects_forged_reported_check():
    certificate, graph, goal, policy = fixture()
    certificate.checks["E"] = False
    result = audit_certificate(
        certificate, graph, [goal], [parse_type("text")], policy,
    )
    assert result.valid is False
    assert result.recomputed["E"] is True
    assert result.matches["E"] is False
    assert result.mismatches == ("E",)


def test_independent_audit_fails_closed_on_unknown_tool():
    certificate, graph, goal, policy = fixture()
    certificate.toolkit = ["missing::tool"]
    result = audit_certificate(
        certificate, graph, [goal], [parse_type("text")], policy,
    )
    assert result.valid is False
    assert result.unknown_tools == ("missing::tool",)
