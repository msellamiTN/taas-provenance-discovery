from types import SimpleNamespace

from taas.certificate import _binding_integrity


def goal(goal_id="g1"):
    return SimpleNamespace(id=goal_id)


def reach(derivations=None, tool_types=None):
    return SimpleNamespace(derivations=derivations or {}, tool_types=tool_types or {})


def test_missing_required_goal_witness_is_rejected():
    violations = _binding_integrity(
        SimpleNamespace(contracts={}), [], [goal()], {}, {}, reach(), []
    )
    assert violations == [{"goal": "g1", "reason": "missing_witness"}]


def test_tool_binding_must_reference_selected_tool_and_actual_producer():
    h = SimpleNamespace(contracts={"srv::read": object()})
    rr = reach(
        {"record[]": SimpleNamespace(kind="tool", edge="srv::read")},
        {"record[]": "srv::read"},
    )
    assert _binding_integrity(h, ["srv::read"], [goal()], {"g1": "record[]"},
                              {"g1": "srv::read"}, rr, []) == []
    rejected = _binding_integrity(h, [], [goal()], {"g1": "record[]"},
                                  {"g1": "srv::read"}, rr, [])
    assert rejected[0]["reason"] == "tool_witness_provenance_mismatch"


def test_model_binding_must_match_real_model_derivation():
    derivation = SimpleNamespace(kind="model", edge="LLM::summarise[g1]")
    rr = reach({"text": derivation})
    h = SimpleNamespace(contracts={})
    edge = SimpleNamespace(id="LLM::summarise[g1]")
    assert _binding_integrity(h, [], [goal()], {"g1": "text"},
                              {"g1": edge.id}, rr, [edge]) == []
    rejected = _binding_integrity(h, [], [goal()], {"g1": "text"},
                                  {"g1": "LLM::summarise[g2]"}, rr, [edge])
    assert rejected[0]["reason"] == "model_binding_provenance_mismatch"


def test_dash_binding_is_only_valid_for_prompt_witness():
    h = SimpleNamespace(contracts={})
    rr = reach({"text": SimpleNamespace(kind="prompt", edge="prompt")})
    assert _binding_integrity(h, [], [goal()], {"g1": "text"},
                              {"g1": "-"}, rr, []) == []
    rejected = _binding_integrity(h, [], [goal()], {"g1": "text"},
                                  {"g1": "arbitrary-edge"}, rr, [])
    assert rejected[0]["reason"] == "prompt_binding_must_be_dash"


def test_uncertain_witness_keeps_provenance_check():
    h = SimpleNamespace(contracts={})
    rr = reach({"record[]": SimpleNamespace(kind="tool", edge="srv::read")},
               {"record[]": "srv::read"})
    assert _binding_integrity(h, ["srv::read"], [goal()], {"g1": "~record[]"},
                              {"g1": "srv::read"}, rr, []) == []
