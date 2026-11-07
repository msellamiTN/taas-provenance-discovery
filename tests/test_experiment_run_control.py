import json
import pytest
from taas.experiments.run_control import (
    RunBlocked, _assert_acyclic, execute_experiment, latest_successes,
    load_dependency_manifest, validate_dependency_manifest,
)

def valid_manifest():
    return {"schema_version": "1.0.0", "programme": "PaMCP",
            "depends_on": {f"E{i}": [] for i in range(1, 23)}}

def test_dependency_graph_rejects_cycles():
    with pytest.raises(RunBlocked, match="Cycle"):
        _assert_acyclic({"E1": ["E2"], "E2": ["E1"]})

def test_dependency_graph_accepts_dag():
    _assert_acyclic({"E1": [], "E2": ["E1"], "E3": ["E1", "E2"]})

def test_dependency_manifest_must_be_explicit(tmp_path):
    with pytest.raises(RunBlocked, match="Missing approved"):
        load_dependency_manifest(tmp_path / "absent.json")

def test_injected_dependency_manifest_is_validated():
    bad = valid_manifest()
    bad["depends_on"]["E1"] = ["E2"]
    bad["depends_on"]["E2"] = ["E1"]
    with pytest.raises(RunBlocked, match="Cycle"):
        validate_dependency_manifest(bad)

def test_dependency_manifest_requires_all_experiments():
    bad = valid_manifest()
    del bad["depends_on"]["E22"]
    with pytest.raises(RunBlocked, match="E1-E22"):
        validate_dependency_manifest(bad)

def test_latest_success_uses_latest_attempt_per_experiment():
    assert latest_successes([{"experiment_id":"E1","status":"completed"},
                             {"experiment_id":"E1","status":"failed"},
                             {"experiment_id":"E2","status":"completed"}]) == {"E2"}

def test_latest_success_rejects_malformed_ledger_records():
    with pytest.raises(RunBlocked, match="Malformed"):
        latest_successes([{"experiment_id":"E1"}])

def test_execution_fails_closed_without_handler(tmp_path):
    with pytest.raises(RunBlocked, match="No validated implementation"):
        execute_experiment("E1", handler=None, input_manifest={}, ledger_path=tmp_path/"runs.jsonl",
                           dependency_manifest=valid_manifest())
    assert not (tmp_path/"runs.jsonl").exists()

def test_execution_requires_explicit_approved_dependency_manifest(tmp_path):
    with pytest.raises(RunBlocked, match="Missing approved"):
        execute_experiment("E1", handler=lambda _: {"status":"completed","artifacts":["x"]},
          input_manifest={"protocol_version":"1.0.0","dataset_snapshot_hash":"abc","code_revision":"deadbeef","seed":0},
          ledger_path=tmp_path/"runs.jsonl")

def test_invalid_injected_manifest_blocks_before_ledger_write(tmp_path):
    bad = valid_manifest()
    bad["depends_on"]["E1"] = ["E1"]
    with pytest.raises(RunBlocked, match="Invalid prerequisite"):
        execute_experiment("E1", handler=lambda _: {"status":"completed","artifacts":["x"]},
          input_manifest={"protocol_version":"1.0.0","dataset_snapshot_hash":"abc","code_revision":"deadbeef","seed":0},
          dependency_manifest=bad, ledger_path=tmp_path/"runs.jsonl")
    assert not (tmp_path/"runs.jsonl").exists()
