from taas.experiments.offline_evaluator import evaluate_payload


def test_dispatcher_e8_uses_protocol_mrr_at_10():
    result = evaluate_payload("E8", {
        "rankings": {"q": [f"t{i}" for i in range(1, 12)]},
        "relevant": {"q": {"t11"}},
    })
    assert result["hit@10"]["value"] == 0.0
    assert result["mrr@10"]["value"] == 0.0


def test_dispatcher_e22_applies_confirmatory_and_exploratory_corrections():
    result = evaluate_payload("E22", {
        "paired_differences": {"a": [1, 1, 1]},
        "confirmatory_p_values": {"a": .01, "b": .02},
        "exploratory_p_values": {"x": .04},
        "rankings": [{"a": 1, "b": 2}, {"a": 1, "b": 2}],
        "bootstrap_values": {"hit": [1, 0, 1]},
        "seed": 7,
    })
    assert result["holm_confirmatory"]["adjusted"]["a"] == .02
    assert result["bh_exploratory"]["adjusted"]["x"] == .04
    assert result["paired_tests"]["a"]["method"] == "exact"
