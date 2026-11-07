import json
import pytest
import taas.experiments.run_control as run_control
from taas.experiments.run_control import (
    RunBlocked, _assert_acyclic, execute_experiment, latest_successes,
    load_dependency_manifest, validate_dependency_manifest,
)

def valid_manifest():
    return {"schema_version": "1.0.0", "programme": "PaMCP",
            "depends_on": {f"E{i}": [] for i in range(1, 23)},
            "external_prerequisites": {f"E{i}": [] for i in range(1, 23)}}

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

def test_execution_requires_explicit_approved_dependency_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(run_control, "DEFAULT_DEPENDENCIES", tmp_path / "absent.json")
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


def test_external_prerequisites_must_define_all_experiments():
    bad = valid_manifest()
    del bad["external_prerequisites"]["E22"]
    with pytest.raises(RunBlocked, match="External prerequisites"):
        validate_dependency_manifest(bad)


def test_execution_fails_closed_without_external_gate_evidence(tmp_path):
    manifest = valid_manifest()
    manifest["external_prerequisites"]["E12"] = ["calibration-set freeze"]
    with pytest.raises(RunBlocked, match="external prerequisites"):
        execute_experiment(
            "E12",
            handler=lambda _: {"status": "completed", "artifacts": ["result.json"]},
            input_manifest={
                "protocol_version": "1.0.0",
                "dataset_snapshot_hash": "a" * 64,
                "code_revision": "deadbeef",
                "seed": 0,
            },
            dependency_manifest=manifest,
            ledger_path=tmp_path / "runs.jsonl",
        )
    assert not (tmp_path / "runs.jsonl").exists()


def test_execution_accepts_hashed_external_gate_evidence(tmp_path):
    manifest = valid_manifest()
    manifest["external_prerequisites"]["E12"] = ["calibration-set freeze"]
    record = execute_experiment(
        "E12",
        handler=lambda _: {"status": "completed", "artifacts": ["e12/result.json"]},
        input_manifest={
            "protocol_version": "1.0.0",
            "dataset_snapshot_hash": "a" * 64,
            "code_revision": "deadbeef",
            "seed": 0,
            "external_gate_evidence": {
                "calibration-set freeze": {
                    "status": "satisfied",
                    "artifact_refs": ["calibration/frozen_manifest.json"],
                    "sha256": "b" * 64,
                }
            },
        },
        dependency_manifest=manifest,
        ledger_path=tmp_path / "runs.jsonl",
    )
    assert record["status"] == "completed"
    assert record["external_prerequisites"] == ["calibration-set freeze"]
    assert record["external_gate_evidence"]["calibration-set freeze"]["sha256"] == "b" * 64


def test_execution_rejects_unhashed_external_gate_evidence(tmp_path):
    manifest = valid_manifest()
    manifest["external_prerequisites"]["E12"] = ["calibration-set freeze"]
    with pytest.raises(RunBlocked, match="external prerequisites"):
        execute_experiment(
            "E12",
            handler=lambda _: {"status": "completed", "artifacts": ["result.json"]},
            input_manifest={
                "protocol_version": "1.0.0",
                "dataset_snapshot_hash": "a" * 64,
                "code_revision": "deadbeef",
                "seed": 0,
                "external_gate_evidence": {
                    "calibration-set freeze": {
                        "status": "satisfied",
                        "artifact_refs": ["calibration/frozen_manifest.json"],
                    }
                },
            },
            dependency_manifest=manifest,
            ledger_path=tmp_path / "runs.jsonl",
        )
    assert not (tmp_path / "runs.jsonl").exists()
