import itertools
import pytest

from taas.experiments.gap_execution_factorial_evaluators import (
    capability_gap_metrics, end_to_end_metrics, prompt_injection_metrics, factorial_effects,
)


def test_capability_gap_metrics_preserve_goal_denominator():
    result = capability_gap_metrics([
        {"toolkit": ["a", "b"], "bridge_ratio": .5, "n_goals": 4,
         "native_goals": 2, "task_success": True},
    ])
    assert result["toolkit_size_mean"] == 2
    assert result["native_goal_share"] == .5
    assert result["bridge_ratio_mean"] == .5


def test_end_to_end_wrong_tool_calls_are_separated_by_category():
    result = end_to_end_metrics([{
        "task_success": True, "steps": 4, "tokens": 100,
        "calls": [{"wrong_tool_category": "irrelevant"},
                  {"wrong_tool_category": "policy_violating"}],
    }])
    assert result["wrong_tool_calls"] == {
        "irrelevant": 1, "invalid_state": 0, "policy_violating": 1,
    }


def test_prompt_injection_exposure_attempt_and_execution_are_distinct():
    result = prompt_injection_metrics([{
        "unsafe_tool_exposed": True, "out_of_policy_attempts": 2,
        "executed_out_of_policy_actions": 0, "task_success": True,
    }])
    assert result["cases_with_unsafe_exposure"] == 1
    assert result["out_of_policy_attempts"] == 2
    assert result["executed_out_of_policy_actions"] == 0


def test_factorial_effects_require_all_eight_cells_and_recover_main_effect():
    rows = []
    for g, p, s in itertools.product((0, 1), repeat=3):
        y = 2 + 3*g + 0*p + 0*s
        rows.append({"G": g, "P": p, "S": s, "observations": [{"score": y}]})
    result = factorial_effects(rows, "score")
    assert result["effects"]["G"] == 3
    assert result["effects"]["P"] == 0
    assert result["effects"]["S"] == 0


def test_factorial_effects_fail_on_missing_cell():
    rows = [{"G": g, "P": p, "S": s, "observations": [{"score": 1}]}
            for g, p, s in itertools.product((0, 1), repeat=3) if (g,p,s) != (1,1,1)]
    with pytest.raises(ValueError, match="missing 2"):
        factorial_effects(rows, "score")
