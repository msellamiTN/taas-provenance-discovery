from experiments.e3_simulation import EFFECTS, FIXTURES, infer_effects, run

def test_all_synthetic_fixtures_match_expected_effects(tmp_path):
    for _, events, expected in FIXTURES:
        assert infer_effects(events) == sorted(expected, key=EFFECTS.index)
    result = run(tmp_path)
    assert result["status"] == "software_validation_only"
    assert result["empirical_evidence"] is False
    assert result["live_mcp_calls"] == 0
    assert result["fixture_exact_matches"] == len(FIXTURES)
    assert (tmp_path / "e3_simulated_trace_fixtures.csv").exists()
    assert (tmp_path / "e3_synthetic_fixture_coverage.svg").exists()
    assert (tmp_path / "e3_simulation_manifest.json").exists()

def test_unmapped_event_fails_closed_to_unknown():
    assert infer_effects(["unrecognized_event"]) == ["unknown"]

def test_multilabel_fixture_preserves_both_effects():
    assert infer_effects(["data_read", "controlled_destination_send"]) == ["read", "egress"]
