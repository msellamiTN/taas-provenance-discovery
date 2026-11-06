from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "experiments" / "colab" / "e1_registry_characterization.py"
SPEC = importlib.util.spec_from_file_location("e1_registry_characterization", RUNNER_PATH)
assert SPEC and SPEC.loader
E1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E1)


def _fixture(root: Path, *, status: str = "planned_not_run") -> None:
    (root / "data" / "processed").mkdir(parents=True)
    (root / "data" / "raw").mkdir(parents=True)
    (root / "docs" / "experiment_design").mkdir(parents=True)
    tool = {
        "server": "srv-a",
        "name": "read_rows",
        "description": "Read rows from a table",
        "input_schema": {
            "type": "object",
            "properties": {"table": {"type": "string"}},
            "required": ["table"],
        },
        "output_schema": {"type": "array", "items": {"type": "object"}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
        "source": "fixture-source-a",
        "category": "database",
        "extra": None,
    }
    tool["id"] = "srv-a::read_rows"
    tool["hash"] = E1.canonical_definition_hash(tool)
    second = {
        "server": "srv-b",
        "name": "write_rows",
        "description": "",
        "input_schema": {},
        "output_schema": None,
        "annotations": None,
        "source": "fixture-source-b",
        "category": "other",
        "extra": None,
        "id": "srv-b::write_rows",
    }
    (root / "data" / "processed" / "registry_merged.json").write_text(
        json.dumps({"registry": [tool, second]}), encoding="utf-8"
    )
    (root / "data" / "raw" / "SOURCES.txt").write_text(
        "fixture-source-a revision-a\nfixture-source-b revision-b\n", encoding="utf-8"
    )
    (root / "docs" / "experiment_design" / "pamcp_experiments_v1.json").write_text(
        json.dumps({
            "experiments": [{
                "id": "E1",
                "title": "Registry characterization",
                "status": status,
            }]
        }),
        encoding="utf-8",
    )


def test_e1_writes_frozen_inputs_summary_tables_and_manifest(tmp_path: Path):
    _fixture(tmp_path)
    run_dir = E1.run_e1(tmp_path, tmp_path / "runs", run_id="synthetic-e1")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "MANIFEST.json").read_text(encoding="utf-8"))

    assert summary["registry"]["tool_rows"] == 2
    assert summary["metadata_completeness"]["published_hash_mismatches"] == 0
    assert summary["guardrails"]["silver_labels_read"] is False
    assert summary["guardrails"]["task_gold_labels_read"] is False
    assert manifest["experiment"]["catalog_status_before_run"] == "planned_not_run"
    assert (run_dir / "category_by_source.csv").is_file()
    assert (run_dir / "annotation_hint_distribution.csv").is_file()
    assert (run_dir / "category_by_source.png").is_file()

    frozen = run_dir / "inputs" / "registry_merged.json.gz"
    with gzip.open(frozen, "rb") as stream:
        original = stream.read()
    source_path = tmp_path / "data" / "processed" / "registry_merged.json"
    assert hashlib.sha256(original).hexdigest() == hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert manifest["inputs"]["registry_sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest()


def test_e1_refuses_to_run_if_catalog_status_is_not_planned(tmp_path: Path):
    _fixture(tmp_path, status="completed")
    with pytest.raises(ValueError, match="planned_not_run"):
        E1.run_e1(tmp_path, tmp_path / "runs", run_id="must-not-run")


def test_e1_does_not_overwrite_an_existing_run_directory(tmp_path: Path):
    _fixture(tmp_path)
    E1.run_e1(tmp_path, tmp_path / "runs", run_id="fixed-run")
    with pytest.raises(FileExistsError):
        E1.run_e1(tmp_path, tmp_path / "runs", run_id="fixed-run")


NOTEBOOK_PATH = ROOT / "notebooks" / "PaMCP_Core_Protocol_v2.ipynb"


def _master_colab_code_cells() -> list[str]:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    assert notebook.get("nbformat") == 4
    return [
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]


def test_master_colab_uses_catalog_matched_descriptive_e1_runner():
    cells = _master_colab_code_cells()
    e1 = next(cell for cell in cells if "Execute the catalog-matched metadata-only E1" in cell)
    assert 'experiments" / "colab" / "e1_registry_characterization.py' in e1
    assert "experiments" / "e1_protocol_runner.py" not in e1
    assert "catalog_status_before_run" in e1
    assert '["inputs"]["registry_sha256"]' in e1
    assert '"scope": "descriptive_registry_characterization_only"' in e1
    assert "independent effect labels" in e1


def test_master_colab_e2_intake_is_preregistered_and_fingerprint_gated():
    cells = _master_colab_code_cells()
    e2 = next(cell for cell in cells if "E2 preparation only" in cell)
    for variable in (
        "PAMCP_E2_SAMPLE_SIZE",
        "PAMCP_E2_SEED",
        "PAMCP_E2_SAMPLING_DESIGN",
    ):
        assert variable in e2
    assert "sha256(e2_registry) == e1_record.get(\"registry_sha256\")" in e2
    assert '"status": "BLOCKED_ORACLE"' in e2
    assert '"status": "PREPARED_NOT_RUN"' in e2
    assert 'e2_manifest.get("llm_silver_labels_used_as_gold") is not False' in e2


def test_master_colab_ledger_uses_runtime_e1_and_e2_statuses():
    cells = _master_colab_code_cells()
    ledger = next(cell for cell in cells if 'run_manifest["experiment_ledger"]=ledger' in cell)
    assert 'ledger["E1"] = run_manifest["results"].get("E1", ledger["E1"])' in ledger
    assert 'ledger["E2"] = run_manifest["results"].get("E2", ledger["E2"])' in ledger
