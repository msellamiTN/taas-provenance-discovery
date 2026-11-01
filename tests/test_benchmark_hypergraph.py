from __future__ import annotations

from taas.benchmark_hypergraph import build_benchmark_hypergraph
from taas.data.registries import RawTool


def _tools():
    return [
        RawTool(
            server="files",
            name="read_file",
            description="Read a file and return its text.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "encoding": {"type": "string"},
                },
                "required": ["path"],
            },
            source="test-benchmark",
            category="filesystem",
        ),
        RawTool(
            server="files",
            name="write_file",
            description="Write content to a file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            source="test-benchmark",
            category="filesystem",
        ),
    ]


def test_builds_one_hyperedge_per_tool_and_retains_named_tail():
    _, graph, _, report = build_benchmark_hypergraph(_tools())
    assert graph["summary"]["n_hyperedges"] == 2
    edges = {e["edge_id"]: e for e in graph["hyperedges"]}
    assert edges["files::read_file"]["tail"] == [{"argument": "path", "type": "path"}]
    assert {x["argument"] for x in edges["files::write_file"]["tail"]} == {"path", "content"}
    assert edges["files::read_file"]["head"]
    assert report["data_leakage_controls"]["gold_tool_labels_used_to_create_hyperedges"] is False


def test_benchmark_gold_mappings_are_separate_and_preserve_ambiguity():
    tasks = {
        "LiveMCPBench": [
            {
                "id": "task-1",
                "query": "Read a local file",
                "source": "LiveMCPBench",
                "category": "filesystem",
                "gold_tools": ["files::read_file|other::read_file"],
                "gold_unresolved": ["unknown_tool"],
                "n_steps": 1,
            }
        ]
    }
    _, graph, benchmark, _ = build_benchmark_hypergraph(_tools(), tasks)
    task = benchmark["tasks"][0]
    assert task["gold_tool_alternatives"] == [["files::read_file", "other::read_file"]]
    assert task["resolved_gold_tool_ids"] == ["files::read_file"]
    assert task["unresolved_gold_tool_ids"] == ["other::read_file"]
    assert task["gold_unresolved_names"] == ["unknown_tool"]
    assert task["usage"] == "evaluation_only_not_used_for_capability_inference"
    assert "tasks" not in graph


def test_task_gold_labels_cannot_change_capability_graph():
    raw = _tools()
    _, graph_a, _, _ = build_benchmark_hypergraph(raw, {})
    _, graph_b, _, _ = build_benchmark_hypergraph(
        raw,
        {"MCPToolBench++": [{
            "id": "gold-label-only",
            "query": "unrelated query",
            "source": "MCPToolBench++",
            "category": "other",
            "gold_tools": ["files::write_file"],
            "gold_unresolved": [],
            "n_steps": 1,
        }]},
    )
    assert graph_a == graph_b
