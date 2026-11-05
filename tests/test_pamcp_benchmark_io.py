from taas.experiments.benchmark_io import (
    complete_set_recall,
    discovery_view,
    normalize_task,
    normalize_tool,
    retrieval_coverage,
    unsafe_exposure_at_k,
    unsafe_share_at_k,
    validate_tool_disjoint,
)


def test_normalize_tool_does_not_invent_effect_labels():
    tool = normalize_tool({
        "id": "srv::tool", "name": "tool", "annotations": {"readOnlyHint": False}
    }, "fixture")
    view = discovery_view(tool)
    assert view["annotations"]["readOnlyHint"] is False
    assert "observed_effects" not in view
    assert "unsafe" not in view


def test_normalize_task_preserves_multiple_acceptable_sets():
    task = normalize_task({
        "task_id": "q1",
        "prompt": "Find the weather",
        "acceptable_tool_sets": [["weather::forecast"], ["search::weather", "weather::read"]],
    }, "fixture")
    assert len(task.acceptable_tool_sets) == 2


def test_safety_metrics_return_none_without_independent_reference():
    rankings = {"q1": ["a", "b"], "q2": ["c"]}
    assert unsafe_exposure_at_k(rankings, None, 2) is None
    assert unsafe_share_at_k(rankings, None, 2) is None


def test_safety_metrics_use_different_denominators():
    rankings = {"q1": ["unsafe", "safe"], "q2": ["safe"]}
    unsafe = {"unsafe"}
    assert unsafe_exposure_at_k(rankings, unsafe, 2) == 0.5
    assert unsafe_share_at_k(rankings, unsafe, 2) == 1 / 3


def test_coverage_uses_fixed_request_denominator_including_abstentions():
    assert retrieval_coverage({"q1": ["a"], "q2": []}, ["q1", "q2", "q3"]) == 1 / 3


def test_complete_set_recall_accepts_any_valid_alternative():
    predictions = {"q1": ["weather::read", "clock::now"]}
    references = {"q1": [["weather::forecast"], ["weather::read", "clock::now"]]}
    assert complete_set_recall(predictions, references) == 1.0


def test_tool_disjoint_split_rejects_overlap():
    train = [normalize_tool({"id": "s::a", "server": "s"}, "d")]
    test = [normalize_tool({"id": "s::b", "server": "s"}, "d")]
    try:
        validate_tool_disjoint(train, test, by_server=True)
    except ValueError as exc:
        assert "server-disjoint" in str(exc)
    else:
        raise AssertionError("Expected server overlap to be rejected")
