import pytest

from taas.experiments.offline_evaluator import evaluate_payload


def test_dispatcher_runs_e1_from_frozen_registry_rows():
    result = evaluate_payload("E1", {"registry_rows": [
        {"tool_id": "a", "server": "s", "category": "x", "definition_hash": "h"},
    ]})
    assert result["n_rows"] == 1
    assert result["n_unique_servers"] == 1


def test_dispatcher_rejects_missing_protocol_payload_fields():
    with pytest.raises(ValueError, match="missing required fields"):
        evaluate_payload("E8", {"rankings": {}})


def test_dispatcher_e10_aggregates_independent_audit_records():
    result = evaluate_payload("E10", {"independent_audits": [
        {"recomputed": {key: True for key in ("S","C","P","E","L","V")}},
        {"recomputed": {key: False for key in ("S","C","P","E","L","V")}},
    ]})
    assert result["overall_conjunction"]["value"] == .5


def test_dispatcher_rejects_unknown_experiment():
    with pytest.raises(KeyError):
        evaluate_payload("E23", {})
