from taas.experiments.provenance_policy_evaluators import (
    effect_discrepancy, probe_coverage, verifier_error_rates,
    trust_threshold_sweep, pareto_frontier, policy_threshold_pareto,
    malicious_provider_exposure_curve, verifier_threshold_sweep,
)


def test_effect_discrepancy_requires_matching_definition_hash():
    result = effect_discrepancy(
        {"a": ["read"], "b": ["write"]},
        {"a": ["read"], "b": ["read"]},
        {"a": "h1", "b": "h2"},
        {"a": "h1", "b": "old-h2"},
    )
    assert result["comparable_tools"] == 1
    assert result["discrepancy_rate"]["value"] == 0.0
    assert result["hash_mismatch_tools"] == 1


def test_probe_coverage_does_not_count_hash_mismatch():
    result = probe_coverage(
        ["a", "b"], {"a": ["read"], "b": ["write"]},
        {"a": "h1", "b": "h2"}, {"a": "h1", "b": "stale"},
        probeable_tool_ids=["a", "b"],
    )
    assert result["probe_coverage"]["numerator"] == 1
    assert result["probe_coverage"]["denominator"] == 2


def test_verifier_far_frr_keep_abstentions_and_unknown_separate():
    result = verifier_error_rates(
        {"a": True, "b": False, "c": None},
        {"a": False, "b": True, "c": True},
    )
    assert result["false_acceptance_rate"]["value"] == 1.0
    assert result["false_rejection_rate"]["value"] == 1.0
    assert result["unknown_reference"] == 1


def test_trust_threshold_sweep_is_monotone_for_fixed_evidence():
    rows = trust_threshold_sweep(
        {"a": {"read_only": 0.9}, "b": {"read_only": 0.5}},
        ["read_only"], [0.25, 0.5, 0.9, 1.0],
    )
    assert [row["eligible_count"] for row in rows] == [2, 2, 1, 0]


def test_pareto_frontier_uses_explicit_objective_directions():
    points = [
        {"utility": 0.8, "exposure": 0.2},
        {"utility": 0.7, "exposure": 0.3},
        {"utility": 0.9, "exposure": 0.4},
    ]
    assert pareto_frontier(points, ["utility"], ["exposure"]) == [0, 2]


def test_policy_threshold_pareto_keeps_threshold_and_coverage():
    sweep = trust_threshold_sweep(
        {"a": {"read_only": 0.9}, "b": {"read_only": 0.5}},
        ["read_only"], [0.5, 0.9],
    )
    result = policy_threshold_pareto(
        sweep, {0.5: 0.2, 0.9: 0.1}, {0.5: 0.9, 0.9: 0.8},
    )
    assert len(result["frontier"]) == 2
    assert result["points"][0]["eligible_share"] == 1.0


def test_malicious_provider_curve_uses_explicit_provider_assignments():
    rows = malicious_provider_exposure_curve(
        {"q1": ["a", "b"]}, {"a": "p1", "b": "p2"},
        {0.5: ["p1"]}, k=1,
    )
    assert rows[0]["Exp@k"]["value"] == 1.0


def test_verifier_threshold_sweep_uses_supplied_risk_scores():
    rows = verifier_threshold_sweep(
        {"unsafe": True, "safe": False},
        {"unsafe": .9, "safe": .1}, [.5, 1.0],
    )
    assert rows[0]["false_acceptance_rate"]["value"] == 0.0
    assert rows[1]["false_acceptance_rate"]["value"] == 1.0


def test_probeable_share_and_probe_coverage_have_distinct_denominators():
    result = probe_coverage(
        ["a", "b", "c"],
        {"a": ["read"], "b": None, "c": None},
        {"a": "h1", "b": "h2", "c": "h3"},
        {"a": "h1"},
        probeable_tool_ids=["a", "b"],
    )
    assert result["probeable_share"]["value"] == 2 / 3
    assert result["probe_coverage"]["value"] == .5
