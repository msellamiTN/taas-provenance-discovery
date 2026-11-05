import json

from taas.experiments.mcp_atlas_adapter import adapt_mcp_atlas_records


def test_mcp_atlas_adapter_preserves_visibility_and_hides_reference_data(tmp_path):
    rows = [{
        "TASK": "task-0001",
        "PROMPT": "Find and summarize the record",
        "ENABLED_TOOLS": json.dumps([
            {"name": "search", "server": "docs", "description": "Search documents",
             "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}},
            {"name": "read", "server": "docs", "description": "Read a document"},
        ]),
        "GTFA_CLAIMS": json.dumps([{"claim": "The record exists"}]),
        "TRAJECTORY": json.dumps([{"tool": "docs::search"}, {"tool": "docs::read"}]),
    }]
    manifest = adapt_mcp_atlas_records(rows, tmp_path)
    discovery = json.loads((tmp_path / "discovery" / "tasks.json").read_text())
    visibility = json.loads((tmp_path / "discovery" / "task_tool_visibility.json").read_text())
    evaluator = json.loads((tmp_path / "evaluator" / "task_references.json").read_text())

    assert len(discovery) == 1
    assert "GTFA_CLAIMS" not in discovery[0]
    assert "TRAJECTORY" not in discovery[0]
    assert len(visibility[0]["enabled_tool_ids"]) == 2
    assert evaluator[0]["gtfa_claims"]
    assert evaluator[0]["trajectory_reference"]
    assert manifest["separation"]["gold_labels_exposed_to_discovery"] is False


def test_mcp_atlas_adapter_rejects_conflicting_same_tool_definitions(tmp_path):
    rows = [
        {"TASK": "t1", "PROMPT": "one", "ENABLED_TOOLS": [{"name": "x", "server": "s", "description": "first"}]},
        {"TASK": "t2", "PROMPT": "two", "ENABLED_TOOLS": [{"name": "x", "server": "s", "description": "different"}]},
    ]
    try:
        adapt_mcp_atlas_records(rows, tmp_path)
    except ValueError as exc:
        assert "Conflicting tool definitions" in str(exc)
    else:
        raise AssertionError("Expected conflicting tool definitions to fail")
