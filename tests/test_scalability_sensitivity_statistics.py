from taas.experiments.scalability_sensitivity_statistics import (
    percentile_summary, scalability_summary, exact_greedy_gap,
    weight_sensitivity, evolution_replay_metrics, percentile_bootstrap,
    paired_sign_flip, adjust_pvalues, rank_stability,
)


def test_scalability_summary_reports_stage_percentiles_and_n():
    result = scalability_summary([
        {"registry_size": 10, "stage": "index", "latency_ms": 2, "memory_mb": 5},
        {"registry_size": 10, "stage": "index", "latency_ms": 4, "memory_mb": 7},
    ])
    row = result["groups"][0]
    assert row["latency_ms"]["p50"] == 3
    assert row["latency_ms"]["p95"] == 3.9
    assert row["latency_ms"]["n"] == 2


def test_exact_greedy_gap_respects_direction():
    assert exact_greedy_gap(100, 110, "minimize")["relative_gap"] == 0.1
    assert exact_greedy_gap(100, 90, "maximize")["relative_gap"] == 0.1


def test_weight_sensitivity_uses_pairwise_jaccard():
    result = weight_sensitivity({"a": ["x", "y"], "b": ["y", "z"]})
    assert result["pairs"][0]["jaccard"] == 1 / 3


def test_evolution_replay_counts_stale_and_false_invalidations():
    result = evolution_replay_metrics([{
        "event_id": "e1", "expected_invalidations": ["a"],
        "actual_invalidations": ["a", "b"], "stale_answers": ["c"],
        "incremental_state": {"x": 1}, "full_recompute_state": {"x": 1},
    }])
    assert result["false_invalidations"] == 1
    assert result["stale_answers"] == 1
    assert result["events_incorrect_vs_recompute"] == 0


def test_bootstrap_is_seed_reproducible_and_reports_n():
    a = percentile_bootstrap([1, 2, 3], replicates=200, seed=42)
    b = percentile_bootstrap([1, 2, 3], replicates=200, seed=42)
    assert a == b
    assert a["n"] == 3
    assert a["ci_width"] >= 0


def test_paired_sign_flip_exact_small_sample():
    result = paired_sign_flip([1, 1, 1])
    assert result["method"] == "exact"
    assert result["p_value"] == 0.25


def test_holm_and_bh_adjustment_are_monotone_and_correct():
    holm = adjust_pvalues({"p3": 0.03, "p1": 0.01, "p2": 0.02}, "holm")["adjusted"]
    assert holm == {"p1": 0.03, "p2": 0.04, "p3": 0.04}
    bh = adjust_pvalues({"p3": 0.03, "p1": 0.01, "p2": 0.02}, "bh")["adjusted"]
    assert bh == {"p1": 0.03, "p2": 0.03, "p3": 0.03}


def test_rank_stability_reports_pairwise_common_tool_count():
    result = rank_stability([{"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 3, "c": 2}])
    assert result["pairs"][0]["n_common"] == 3
    assert result["mean_pairwise_rank_correlation"] == 0.5
