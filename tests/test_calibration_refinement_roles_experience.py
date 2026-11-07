from taas.experiments.calibration_refinement_roles_experience import (
    model_profile_calibration, refinement_metrics, role_configuration_metrics,
    experience_reuse_metrics,
)


def test_calibration_pairs_claims_and_reports_refutation():
    result = model_profile_calibration([
        {"class": "summarise", "n": 5, "correct": True, "claimed_rho": .95},
        {"class": "summarise", "n": 5, "correct": False, "claimed_rho": .95},
        {"class": "summarise", "n": 5, "correct": False},
    ], tau=.9, replicates=100)
    assert result["refuted_claims"] == 1
    assert result["claim_denominator"] == 2
    assert result["mean_absolute_calibration_gap"] == .5


def test_refinement_metrics_are_grouped_by_counterexample():
    result = refinement_metrics([
        {"chi": "chi1", "repair_success": True, "abstained": False, "iterations": 2, "tokens": 100},
        {"chi": "chi1", "repair_success": False, "abstained": True, "iterations": 3, "tokens": 150},
    ])
    assert result["by_chi"]["chi1"]["repair_success_rate"] == .5
    assert result["by_chi"]["chi1"]["abstention_rate"] == .5


def test_role_configuration_metrics_report_all_required_outcomes():
    result = role_configuration_metrics([
        {"role_configuration": "single", "goalspec_valid": True, "repaired": False,
         "task_success": True, "tokens": 100, "latency_ms": 200},
        {"role_configuration": "single", "goalspec_valid": False, "repaired": True,
         "task_success": False, "tokens": 120, "latency_ms": 250},
    ])
    assert result["roles"]["single"]["goalspec_validity_rate"] == .5
    assert result["roles"]["single"]["task_success_rate"] == .5


def test_experience_reuse_metrics_requires_confirmed_record_fields():
    result = experience_reuse_metrics([
        {"reused": True, "cold_latency_ms": 100, "reuse_latency_ms": 40,
         "stale_evidence": True, "stale_error_caught": True},
        {"reused": False, "stale_evidence": True, "stale_error_caught": False},
    ])
    assert result["reuse_rate"] == .5
    assert result["latency_saved_ms"]["mean"] == 60
    assert result["stale_errors_uncaught"] == 1
