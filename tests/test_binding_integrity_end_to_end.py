"""End-to-end regression tests for witness binding integrity.

These drive the real request path (DiscoveryEngine.discover -> Composer -> certify) instead of
mocked reach results, so they catch mismatches between what certify() records and what
_binding_integrity() expects. Each valid case below was rejected by the first version of the
binding check (all three abstained with a chi1 "uncovered capability").
"""
from __future__ import annotations

import pytest

from taas.certificate import _binding_integrity, certify
from taas.composer import ComposerConfig
from taas.contracts import make_contract
from taas.engine import DiscoveryEngine, EngineConfig
from taas.goals import parse_goal_spec
from taas.policy import Policy
from taas.scenarios import SCENARIOS, illustrative_profile

POLICY = Policy.make("open", required=(), allowed=("read(*)", "egress(*)", "write(*)"), lmin=0.0,
                     forbidden_pairs=())
REGISTRY = [
    make_contract("fs::read_file", {"path": "path"}, "text", ["read(fs)"], "obs", tool_class="retrieve"),
    make_contract("whois::lookup", {"d": "identifier:whois"}, "record:whois", ["read(web)", "egress(whois)"],
                  "obs", tool_class="retrieve"),
]

VALID = {
    # a gap goal whose output type is also a prompt input type (prompt supplies `text`)
    "tool_output_shares_prompt_type": (
        {"prompt_inputs": ["text", "path"], "goals": [
            {"id": "g1", "class": "retrieve", "in": ["path"], "out": "text", "eff": ["read(fs)"], "sigma": "data"}]},
        ["fs::read_file"]),
    # a native answer goal discharged by text already in context, after a tool goal
    "native_goal_after_tool_goal": (
        {"prompt_inputs": ["text", "identifier:whois"], "goals": [
            {"id": "g1", "class": "retrieve", "in": ["identifier:whois"], "out": "record:whois",
             "eff": ["read(web)"], "sigma": "data"},
            {"id": "g2", "class": "answer", "in": ["text", "record:whois"], "out": "text", "sigma": "native",
             "deps": ["g1"]}]},
        ["whois::lookup"]),
    # model-only coverage: the empty toolkit is a valid, certified answer
    "model_only_empty_toolkit": (
        {"prompt_inputs": ["text"], "goals": [
            {"id": "g1", "class": "write", "in": ["text"], "out": "text", "sigma": "native"}]},
        []),
}


@pytest.mark.parametrize("name", list(VALID))
def test_valid_selection_is_certified(name):
    spec, expected = VALID[name]
    r = DiscoveryEngine(REGISTRY, illustrative_profile(), pair_policy=POLICY).discover(spec, POLICY)
    assert r.toolkit == expected, r.counterexample and r.counterexample.to_dict()
    assert r.certificate.valid
    assert r.certificate.witnesses["binding_integrity"] == {"valid": True, "violations": []}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_paper_scenarios_have_clean_binding_integrity(name):
    reg, spec, pol, exp = SCENARIOS[name]
    r = DiscoveryEngine(reg(), illustrative_profile(), pair_policy=pol()).discover(spec(), pol())
    assert sorted(r.toolkit) == sorted(exp["toolkit"])
    assert r.certificate.witnesses["binding_integrity"]["valid"]


def _certify(spec_dict, K):
    eng = DiscoveryEngine(REGISTRY, illustrative_profile(), cfg=EngineConfig(ComposerConfig()), pair_policy=POLICY)
    spec = parse_goal_spec(spec_dict)
    gr = eng.gap(spec)
    medges = eng.composer.model_edges(spec.goals)
    return certify(eng.H, K, spec.goals, spec.prompt_inputs, POLICY, medges, eng.profile, regime="test",
                   cost=0.0, util=1.0)


def test_gap_goal_cannot_be_discharged_by_the_prompt():
    """With no tool selected, the gap goal's `text` output exists only as prompt input: reject."""
    spec, _ = VALID["tool_output_shares_prompt_type"]
    cert = _certify(spec, [])
    assert not cert.valid


def test_binding_to_unselected_tool_is_rejected():
    spec, _ = VALID["native_goal_after_tool_goal"]
    eng = DiscoveryEngine(REGISTRY, illustrative_profile(), pair_policy=POLICY)
    gs = parse_goal_spec(spec)
    eng.gap(gs)
    rr = eng.H.reach(["whois::lookup"], gs.prompt_inputs, eng.composer.model_edges(gs.goals), eng.profile)
    gap_goal = gs.goals[0]
    v = _binding_integrity(eng.H, [], [gap_goal], {"g1": "record:whois"}, {"g1": "whois::lookup"}, rr,
                           eng.composer.model_edges(gs.goals))
    assert v and v[0]["reason"] == "tool_witness_provenance_mismatch"


def test_gap_goal_bound_to_prompt_is_rejected():
    spec, _ = VALID["tool_output_shares_prompt_type"]
    eng = DiscoveryEngine(REGISTRY, illustrative_profile(), pair_policy=POLICY)
    gs = parse_goal_spec(spec)
    eng.gap(gs)
    rr = eng.H.reach([], gs.prompt_inputs, [], eng.profile)
    v = _binding_integrity(eng.H, [], [gs.goals[0]], {"g1": "text"}, {"g1": "prompt"}, rr, [])
    assert v and v[0]["reason"] == "gap_goal_bound_to_prompt"


def test_certificate_rejection_is_typed_by_failed_check():
    """A selection rejected for an invalid certificate reports a counterexample typed by the check."""
    from taas.certificate import Certificate
    from taas.composer import ComposeResult
    eng = DiscoveryEngine(REGISTRY, illustrative_profile(), pair_policy=POLICY)
    bad = Certificate(["fs::read_file"], {"S": True, "C": True, "P": True, "E": False, "L": True, "V": True,
                                          "M": True, "B": True}, {}, "exact", 1.0, 1.0, 0.0, {})
    orig = eng.composer.compose
    eng.composer.compose = lambda *a, **k: ComposeResult(["fs::read_file"], bad, None, ["fs::read_file"], "exact", {})
    try:
        r = eng.discover(VALID["tool_output_shares_prompt_type"][0], POLICY, refine_on_failure=False)
    finally:
        eng.composer.compose = orig
    assert r.toolkit is None and r.counterexample.kind == "chi2"
    assert r.counterexample.witness["failed_checks"] == ["E"]
