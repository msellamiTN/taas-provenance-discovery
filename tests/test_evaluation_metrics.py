from taas.experiments.evaluation_metrics import (
    binary_classification_metrics, retrieval_metrics, exposure_at_k,
    multi_tool_set_metrics, qos_evidence_record,
)


def test_binary_metrics_keep_unknown_and_abstention_separate():
    result = binary_classification_metrics(
        {"a": True, "b": False, "c": True, "d": None},
        {"a": True, "b": True, "c": None, "d": False},
    )
    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 0)
    assert result["unknown_reference"] == 1
    assert result["abstentions"] == 1
    assert result["prediction_coverage"]["numerator"] == 2
    assert result["prediction_coverage"]["denominator"] == 3


def test_retrieval_metrics_use_exact_request_set():
    result = retrieval_metrics(
        {"q1": ["x", "a"], "q2": ["b"]},
        {"q1": {"a"}, "q2": {"b"}},
    )
    assert result["hit@1"]["value"] == 0.5
    assert result["hit@5"]["value"] == 1.0
    assert result["mrr"]["value"] == 0.75


def test_exposure_uses_independent_unsafe_reference():
    metric = exposure_at_k(
        {"q1": ["safe", "unsafe"], "q2": ["safe"]},
        {"q1": {"unsafe"}, "q2": {"unsafe"}},
        k=1,
    )
    assert metric.value == 0.0
    assert metric.denominator == 2


def test_multi_tool_group_coverage_is_not_task_success():
    result = multi_tool_set_metrics(
        {"q1": {"a", "c"}},
        {"q1": [{"a", "b"}, {"c"}]},
    )
    assert result["group_recall"]["value"] == 1.0
    assert result["complete_set_share"]["value"] == 1.0
    assert "not independent joint-feasibility" in result["interpretation_limit"]


def test_qos_does_not_upgrade_declared_to_measured():
    record = qos_evidence_record(
        metric="latency", value=120, unit="ms",
        evidence_kind="declared", source="provider-manifest",
    )
    assert record["measured"] is False
    assert record["evidence_kind"] == "declared"


def test_observed_qos_requires_definition_binding():
    try:
        qos_evidence_record(metric="latency", value=10, unit="ms",
                            evidence_kind="observed", source="probe")
    except ValueError:
        return
    raise AssertionError("observed QoS without definition hash must fail")
