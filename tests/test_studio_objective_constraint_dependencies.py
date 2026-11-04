from copy import deepcopy

from taas.studio.api import canonicalize_objective_constraint_dependencies


def _contract():
    return {
        "constraints": {
            "inputs": {
                "source_data_required": True,
                "user_supplied_content": False,
            },
            "scope": {
                "all_matching_items": False,
                "date_or_range_constraint": False,
            },
        }
    }


def test_objective_constraint_name_is_not_a_goal_dependency():
    contract = _contract()
    original_contract = deepcopy(contract)
    spec = {
        "prompt": "Retrieve records from the configured source.",
        "goals": [
            {
                "id": "g1",
                "class": "retrieve",
                "deps": ["source_data_required"],
            }
        ],
    }

    normalized, events = canonicalize_objective_constraint_dependencies(spec, contract)

    assert normalized["goals"][0]["deps"] == []
    assert events == [
        {
            "path": "goals[0].deps",
            "from": ["source_data_required"],
            "to": [],
            "removed": ["source_data_required"],
            "rule": "objective_constraint_name_not_goal_dependency",
            "reason": (
                "The removed value names an Objective Contract constraint, not a GoalSpec goal ID. "
                "The constraint remains preserved in the Objective Contract."
            ),
        }
    ]
    assert contract == original_contract
    assert spec["goals"][0]["deps"] == ["source_data_required"]


def test_constraint_repair_preserves_valid_goal_edges_and_unknown_dependencies():
    contract = _contract()
    spec = {
        "goals": [
            {"id": "g1", "deps": ["g0", "source_data_required", "unresolved_goal"]},
            {"id": "g0", "deps": []},
        ]
    }

    normalized, events = canonicalize_objective_constraint_dependencies(spec, contract)

    assert normalized["goals"][0]["deps"] == ["g0", "unresolved_goal"]
    assert normalized["goals"][1]["deps"] == []
    assert len(events) == 1
    assert events[0]["removed"] == ["source_data_required"]


def test_constraint_repair_does_not_remove_non_constraint_unknown_dependency():
    spec = {"goals": [{"id": "g1", "deps": ["source_data_missing"]}]}

    normalized, events = canonicalize_objective_constraint_dependencies(spec, _contract())

    assert normalized == spec
    assert events == []


def test_constraint_repair_is_noop_without_objective_contract_constraints():
    spec = {"goals": [{"id": "g1", "deps": ["source_data_required"]}]}

    normalized, events = canonicalize_objective_constraint_dependencies(spec, None)

    assert normalized == spec
    assert events == []


def test_core_gap_classifies_retrieval_as_tool_required_not_model_skill_gap():
    from types import SimpleNamespace

    from taas.studio.api import classify_core_gap_requirements

    goals = [SimpleNamespace(id="g1", cls="retrieve")]
    result = classify_core_gap_requirements(goals, ["g1"])

    assert result == {
        "status": "tool_requirements_detected",
        "tool_required_goal_ids": ["g1"],
        "model_capability_gap_goal_ids": [],
    }


def test_core_gap_keeps_uncovered_native_skill_separate_from_tool_requirement():
    from types import SimpleNamespace

    from taas.studio.api import classify_core_gap_requirements

    goals = [
        SimpleNamespace(id="g1", cls="retrieve"),
        SimpleNamespace(id="g2", cls="summarise"),
    ]
    result = classify_core_gap_requirements(goals, ["g1", "g2"])

    assert result == {
        "status": "tool_and_model_capability_gaps_detected",
        "tool_required_goal_ids": ["g1"],
        "model_capability_gap_goal_ids": ["g2"],
    }


def test_core_gap_reports_only_native_capability_gap_when_no_external_goal_is_missing():
    from types import SimpleNamespace

    from taas.studio.api import classify_core_gap_requirements

    goals = [SimpleNamespace(id="g1", cls="summarise")]
    result = classify_core_gap_requirements(goals, ["g1"])

    assert result == {
        "status": "capability_gap_detected",
        "tool_required_goal_ids": [],
        "model_capability_gap_goal_ids": ["g1"],
    }


def test_core_gap_classification_does_not_change_gap_membership():
    from types import SimpleNamespace

    from taas.studio.api import classify_core_gap_requirements

    goals = [
        SimpleNamespace(id="g1", cls="retrieve"),
        SimpleNamespace(id="g2", cls="summarise"),
        SimpleNamespace(id="g3", cls="translate"),
    ]
    gap_ids = ["g1", "g2"]
    result = classify_core_gap_requirements(goals, gap_ids)

    assert set(result["tool_required_goal_ids"] + result["model_capability_gap_goal_ids"]) == set(gap_ids)
    assert result["status"] == "tool_and_model_capability_gaps_detected"
