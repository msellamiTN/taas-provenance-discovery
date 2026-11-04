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
