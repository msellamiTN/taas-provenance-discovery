import json
from pathlib import Path

import pytest

from experiments.e9_retrieval_campaign import (
    DECOMPOSITIONS,
    _result_ranking,
    evaluate_equivalence_groups,
    load_discovery_package,
    load_goal_specs,
    validate_release_gate,
)
from taas.experiments.baseline_runner import BaselineResult


def _json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_discovery_package_load_does_not_require_or_open_evaluator_references(tmp_path):
    root = tmp_path / "prepared"
    _json(root / "PREPARATION_MANIFEST.json", {
        "experiment_id": "E9",
        "status": "prepared_not_run",
    })
    _json(root / "discovery" / "tools.json", [
        {"tool_id": "srv::a", "definition_hash": "abc"},
        {"tool_id": "srv::b", "definition_hash": "def"},
    ])
    _jsonl(root / "discovery" / "tasks.jsonl", [
        {"task_id": "t1", "prompt": "Find public information."},
    ])
    _jsonl(root / "discovery" / "task_visibility.jsonl", [
        {"task_id": "t1", "visible_tool_ids": ["srv::a", "srv::b"]},
    ])
    # There is intentionally no evaluator/ directory in this fixture.
    tools, tasks, visibility, manifest = load_discovery_package(root)
    assert [row["tool_id"] for row in tools] == ["srv::a", "srv::b"]
    assert tasks[0]["task_id"] == "t1"
    assert visibility[0]["visible_tool_ids"] == ["srv::a", "srv::b"]
    assert manifest["status"] == "prepared_not_run"


def test_discovery_package_rejects_evaluator_fields(tmp_path):
    root = tmp_path / "prepared"
    _json(root / "PREPARATION_MANIFEST.json", {
        "experiment_id": "E9",
        "status": "prepared_not_run",
    })
    _json(root / "discovery" / "tools.json", [{"tool_id": "srv::a"}])
    _jsonl(root / "discovery" / "tasks.jsonl", [{
        "task_id": "t1", "prompt": "Find a record.",
        "acceptable_tool_sets": [["srv::a"]],
    }])
    _jsonl(root / "discovery" / "task_visibility.jsonl", [{
        "task_id": "t1", "visible_tool_ids": ["srv::a"],
    }])
    with pytest.raises(ValueError, match="evaluator-only"):
        load_discovery_package(root)


def test_goal_spec_loader_requires_all_decomposition_conditions_and_freeze_provenance(tmp_path):
    prompt = "Find the latest public filings and summarize them."
    task = [{"task_id": "t1", "prompt": prompt}]
    rows = []
    (tmp_path / "splitter.py").write_text("# frozen clause splitter\\n")
    (tmp_path / "analyst_prompt.txt").write_text("You are an analyst.")
    (tmp_path / "analyst_response.json").write_text('{"goals": []}')
    import hashlib
    file_hash = lambda name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
    metadata = {
        "none": {"status": "frozen", "transform": "unsegmented_single_goal"},
        "clause_splitter": {
            "status": "frozen", "splitter_version": "cs-1",
            "splitter_path": "splitter.py", "splitter_sha256": file_hash("splitter.py"),
        },
        "llm_analyst": {
            "status": "frozen", "model_id": "analyst",
            "model_revision": "rev-1",
            "prompt_path": "analyst_prompt.txt", "prompt_sha256": file_hash("analyst_prompt.txt"),
            "raw_response_path": "analyst_response.json", "raw_response_sha256": file_hash("analyst_response.json"),
        },
    }
    for mode in DECOMPOSITIONS:
        goals = [{
            "id": "g1", "class": "retrieve", "in": ["text"],
            "out": "record:filing[]", "desc": "retrieve filings",
        }]
        if mode != "none":
            goals.append({
                "id": "g2", "class": "summarise", "in": ["record:filing[]"],
                "out": "text", "desc": "summarize filings", "deps": ["g1"],
            })
        rows.append({
            "task_id": "t1",
            "decomposition": mode,
            "prompt": prompt,
            "prompt_sha256": __import__("hashlib").sha256(prompt.encode()).hexdigest(),
            "evaluator_reference_accessed": False,
            "freeze_metadata": metadata[mode],
            "goal_spec": {"prompt_inputs": ["text"], "goals": goals},
        })
    path = tmp_path / "goals.jsonl"
    _jsonl(path, rows)
    specs = load_goal_specs(path, task)
    assert set(specs) == {("t1", mode) for mode in DECOMPOSITIONS}
    assert len(specs[("t1", "none")].goals) == 1
    assert len(specs[("t1", "llm_analyst")].goals) == 2


def test_goal_spec_loader_rejects_evaluator_access_and_incomplete_matrix(tmp_path):
    prompt = "Read this request."
    row = {
        "task_id": "t1", "decomposition": "none",
        "prompt": prompt,
        "prompt_sha256": __import__("hashlib").sha256(prompt.encode()).hexdigest(),
        "evaluator_reference_accessed": True,
        "freeze_metadata": {"status": "frozen", "transform": "unsegmented_single_goal"},
        "goal_spec": {"goals": [{"id": "g1", "class": "retrieve", "out": "record"}]},
    }
    path = tmp_path / "goals.jsonl"
    _jsonl(path, [row])
    with pytest.raises(ValueError, match="evaluator access"):
        load_goal_specs(path, [{"task_id": "t1", "prompt": prompt}])


def test_release_gate_blocks_when_any_prerequisite_is_not_accepted(tmp_path):
    gate = {
        "schema_version": "1.0.0",
        "status": "accepted",
        "prerequisites": {
            "E1": {"status": "accepted"},
            "E2": {"status": "proposed_not_frozen"},
            "E3": {"status": "accepted"},
            "E12": {"status": "accepted"},
        },
    }
    gate_path = tmp_path / "release_gate.json"
    _json(gate_path, gate)
    comparator_path = tmp_path / "comparators.json"
    _json(comparator_path, {"schema_version": "1.0.0", "status": "accepted"})
    with pytest.raises(ValueError, match="E2 prerequisite is not accepted"):
        validate_release_gate(gate_path, comparator_path)


def test_result_ranking_preserves_method_order_and_rejects_duplicates():
    result = BaselineResult(
        "rag_mcp", "completed",
        selected_tools=["srv::a", "srv::b"],
        ranking=[
            {"tool_id": "srv::b", "rank": 1},
            {"tool_id": "srv::a", "rank": 2},
        ],
    )
    assert _result_ranking(result, 1) == ["srv::b"]
    duplicate = BaselineResult("rag_mcp", "completed", selected_tools=["srv::a", "srv::a"])
    with pytest.raises(ValueError, match="duplicate"):
        _result_ranking(duplicate, 20)


def test_toolscope_oracle_scores_only_independently_adjudicated_pairs():
    oracle = {
        "sha256": "a" * 64,
        "positive_pairs": [["srv::a", "srv::b"]],
        "negative_pairs": [["srv::a", "srv::c"]],
    }
    scored = evaluate_equivalence_groups([["srv::a", "srv::b", "srv::c"]], oracle)
    assert scored["status"] == "scored"
    assert scored["true_positive_merges"] == 1
    assert scored["false_equivalence_merges"] == 1
    assert scored["merge_precision"] == 0.5
    assert scored["merge_recall"] == 1.0
    assert evaluate_equivalence_groups([], None)["status"] == "blocked_missing_independent_equivalence_oracle"
