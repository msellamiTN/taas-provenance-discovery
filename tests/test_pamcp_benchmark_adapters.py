import json

from taas.experiments.benchmark_adapters import adapt_json_export


def test_adapter_separates_discovery_from_evaluator_references(tmp_path):
    tools = tmp_path / "tools.json"
    tasks = tmp_path / "tasks.json"
    out = tmp_path / "out"
    tools.write_text(json.dumps({"tools": [{"id": "srv::read", "name": "read"}]}))
    tasks.write_text(json.dumps({"tasks": [{
        "task_id": "q1",
        "prompt": "Read a record",
        "target_tool_ids": ["srv::read"],
        "acceptable_tool_sets": [["srv::read"]],
    }]}))

    manifest = adapt_json_export("fixture", tools, tasks, out)
    discovery_task = json.loads((out / "discovery" / "tasks.json").read_text())[0]
    evaluator_task = json.loads((out / "evaluator" / "task_references.json").read_text())[0]

    assert "target_tool_ids" not in discovery_task
    assert "acceptable_tool_sets" not in discovery_task
    assert evaluator_task["target_tool_ids"] == ["srv::read"]
    assert manifest["separation"]["gold_labels_exposed_to_discovery"] is False
