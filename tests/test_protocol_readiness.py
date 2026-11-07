from taas.experiments.protocol_readiness import (
    assess_experiment_readiness, assess_programme_readiness,
)


def test_readiness_requires_artifacts_dependencies_and_external_gate():
    result = assess_experiment_readiness(
        "E10",
        available_artifacts=["frozen_graph_and_goal_inputs", "independent_certificate_audits"],
        completed_experiments=["E2", "E3"],
    )
    assert result["status"] == "blocked_missing_inputs_or_gates"
    assert result["missing_dependencies"] == ["E9"]
    assert result["missing_artifacts"] == []


def test_readiness_does_not_mutate_canonical_protocol_status():
    result = assess_experiment_readiness(
        "E1", available_artifacts=["frozen_registry_snapshot", "independent_non_read_only_reference_labels"],
    )
    assert result["status"] == "ready_for_offline_evaluation"
    assert result["protocol_status_mutated"] is False


def test_programme_readiness_always_reports_all_22_experiments():
    result = assess_programme_readiness(available_artifacts=[])
    assert len(result) == 22
    assert result[0]["experiment_id"] == "E1"
    assert result[-1]["experiment_id"] == "E22"
