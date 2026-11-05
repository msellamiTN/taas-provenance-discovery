from taas.experiments.evaluation_metrics import (
    assurance_error_rates,
    bootstrap_mean_ci,
    paired_cluster_bootstrap_ci,
    ranking_metrics,
)


def test_ranking_metrics_include_abstentions_as_empty_rankings():
    result = ranking_metrics(
        {"q1": ["a", "b"], "q2": []},
        {"q1": {"a": 2, "b": 1}, "q2": {"c": 1}},
        ks=(1, 2),
    )
    assert result["metrics"]["1"]["hit@1"]["value"] == 0.5
    assert result["metrics"]["1"]["recall@1"]["value"] == 0.5
    assert result["metrics"]["2"]["precision@2"]["value"] == 0.5
    assert result["queries_with_qrels"] == 2


def test_assurance_error_rates_require_independent_oracle():
    assert assurance_error_rates({"c1": True}, None)["false_assurance_rate"] is None
    result = assurance_error_rates(
        {"valid": False, "invalid": True},
        {"valid": True, "invalid": False},
    )
    assert result["false_assurance_rate"] == 1.0
    assert result["false_rejection_rate"] == 1.0


def test_bootstrap_is_reproducible_and_clustered():
    values = [0.0, 1.0, 1.0, 0.0]
    first = bootstrap_mean_ci(values, resamples=1000, seed=42)
    second = bootstrap_mean_ci(values, resamples=1000, seed=42)
    assert first == second

    left = {"a": 0.0, "b": 0.0, "c": 0.0}
    right = {"a": 1.0, "b": 1.0, "c": 1.0}
    clusters = {"a": "server1", "b": "server1", "c": "server2"}
    ci = paired_cluster_bootstrap_ci(left, right, clusters, resamples=1000, seed=3)
    assert ci["estimate"] == 1.0
    assert ci["n_clusters"] == 2
    assert ci["resampling_unit"] == "cluster"
