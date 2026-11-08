import json
from pathlib import Path

import pytest

from experiments.e9_retrieval_campaign import (
    DECOMPOSITIONS,
    _result_ranking,
    evaluate_equivalence_groups,
    load_discovery_package,
    load_goal_specs,
    load_composer_config,
    load_training_scenes,
    make_no_backward_closure_config,
    canonical_sha256,
    load_encoder,
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


def test_composer_parameters_are_loaded_only_from_approved_e9_config(tmp_path):
    from dataclasses import asdict
    from taas.composer import ComposerConfig

    config = asdict(ComposerConfig(K=20))
    path = tmp_path / "composer.json"
    _json(path, {
        "schema_version": "1.0.0",
        "status": "accepted",
        "experiment_id": "E9",
        "approval_record": "protocol-approval-2026-11",
        "composer": config,
        "refine_k": 3,
    })
    loaded, refine_k, meta = load_composer_config(path)
    assert loaded.K == 20
    assert refine_k == 3
    assert meta["composer"]["K"] == 20

    config["K"] = 10
    _json(path, {
        "schema_version": "1.0.0",
        "status": "accepted",
        "experiment_id": "E9",
        "approval_record": "protocol-approval-2026-11",
        "composer": config,
        "refine_k": 3,
    })
    with pytest.raises(ValueError, match="K=20"):
        load_composer_config(path)


def test_no_backward_closure_changes_only_depth():
    from dataclasses import asdict
    from taas.composer import ComposerConfig

    full = ComposerConfig(K=20, depth=3, relevance=7.5, beta=0.25)
    no_backward = make_no_backward_closure_config(full)
    full_values = asdict(full)
    no_backward_values = asdict(no_backward)
    assert no_backward.depth == 0
    full_values.pop("depth")
    no_backward_values.pop("depth")
    assert full_values == no_backward_values


def test_colt_scenes_are_dev_only_and_built_from_server_membership_crosswalk(tmp_path):
    crosswalk = {"mcp::search": "live::search", "mcp::read": "live::read"}
    bundle = {
        "schema_version": "1.0.0",
        "status": "accepted",
        "source_dataset": "MCPToolBench++",
        "source_split": "dev",
        "scene_source": "server_membership",
        "e9_evaluator_labels_used": False,
        "crosswalk_sha256": canonical_sha256(crosswalk),
        "tool_crosswalk": crosswalk,
        "source_tool_servers": {"mcp::search": "server-a", "mcp::read": "server-a"},
        "dev_query_server_membership": [
            {"task_id": "dev-001", "split": "dev", "server_ids": ["server-a"]},
        ],
    }
    path = tmp_path / "colt-scenes.json"
    _json(path, bundle)
    scenes = load_training_scenes(path, {"live::search", "live::read"}, {"e9-task-1"})
    assert len(scenes) == 1
    assert set(scenes[0]["tools"]) == {"live::search", "live::read"}
    assert scenes[0]["split"] == "train"
    assert scenes[0]["scene_source"] == "server_membership"


def test_colt_scene_crosswalk_hash_must_match(tmp_path):
    path = tmp_path / "colt-scenes.json"
    _json(path, {
        "schema_version": "1.0.0", "status": "accepted",
        "source_dataset": "MCPToolBench++", "source_split": "dev",
        "scene_source": "server_membership", "e9_evaluator_labels_used": False,
        "crosswalk_sha256": "0" * 64, "tool_crosswalk": {"mcp::x": "live::x"},
        "source_tool_servers": {"mcp::x": "s1"},
        "dev_query_server_membership": [{"task_id": "d1", "split": "dev", "server_ids": ["s1"]}],
    })
    with pytest.raises(ValueError, match="crosswalk SHA-256 mismatch"):
        load_training_scenes(path, {"live::x"}, {"e9-1"})


def test_encoder_bundle_requires_complete_hash_bound_snapshot_inventory(tmp_path):
    import hashlib

    model = tmp_path / "model"
    model.mkdir()
    config = model / "config.json"
    weights = model / "weights.bin"
    config.write_text('{"model_type":"test"}', encoding="utf-8")
    weights.write_bytes(b"pinned-weights")

    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    bundle_path = tmp_path / "encoder.json"
    _json(bundle_path, {
        "schema_version": "1.0.0",
        "status": "accepted",
        "provider": "sentence-transformers-local",
        "model_id": "test/model",
        "model_revision": "immutable-revision",
        "package_version": "5.0.0",
        "model_path": "model",
        "files": {
            "config.json": digest(config),
            "weights.bin": digest(weights),
        },
    })

    encoder, metadata = load_encoder(bundle_path, "cpu")
    assert encoder.expected_package_version == "5.0.0"
    assert metadata["files_verified"] == 2

    # Any extra file can alter tokenizer/model loading behaviour and must be frozen.
    (model / "tokenizer_config.json").write_text('{"padding_side":"left"}', encoding="utf-8")
    with pytest.raises(ValueError, match="inventory differs"):
        load_encoder(bundle_path, "cpu")


def test_encoder_bundle_rejects_path_traversal(tmp_path):
    import hashlib

    model = tmp_path / "model"
    model.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    _json(tmp_path / "encoder.json", {
        "schema_version": "1.0.0",
        "status": "accepted",
        "provider": "sentence-transformers-local",
        "model_id": "test/model",
        "model_revision": "immutable-revision",
        "package_version": "5.0.0",
        "model_path": "model",
        "files": {"../outside.bin": hashlib.sha256(outside.read_bytes()).hexdigest()},
    })
    with pytest.raises(ValueError, match="Unsafe encoder manifest path"):
        load_encoder(tmp_path / "encoder.json", "cpu")


def test_release_gate_requires_acceptance_id_for_each_accepted_prerequisite(tmp_path):
    import hashlib

    artifact = tmp_path / "accepted-artifact.json"
    artifact.write_text('{"status":"accepted"}', encoding="utf-8")
    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    prereqs = {
        experiment: {
            "status": "accepted",
            "artifact_path": str(artifact),
            "sha256": artifact_sha,
            "acceptance_id": "acceptance-" + experiment,
        }
        for experiment in ("E1", "E2", "E3", "E12")
    }
    prereqs["E3"].pop("acceptance_id")
    gate_path = tmp_path / "release-gate.json"
    _json(gate_path, {
        "schema_version": "1.0.0",
        "status": "accepted",
        "prerequisites": prereqs,
    })
    comparator_path = tmp_path / "comparators.json"
    _json(comparator_path, {})
    with pytest.raises(ValueError, match="E3 accepted prerequisite must carry"):
        validate_release_gate(gate_path, comparator_path)
