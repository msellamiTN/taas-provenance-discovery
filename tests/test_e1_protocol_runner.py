import csv
import importlib.util
import json
import shutil
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "e1_protocol_runner.py"
SPEC = importlib.util.spec_from_file_location("e1_protocol_runner", SCRIPT)
assert SPEC and SPEC.loader
E1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E1)


def _write_synthetic_source_tree(root: Path) -> None:
    raw = root / "data" / "raw"
    live_root = raw / "livemcpbench"
    pp_root = raw / "mcptoolbenchpp"
    live_root.mkdir(parents=True)
    pp_root.mkdir(parents=True)
    (raw / "SOURCES.txt").write_text(
        "LiveMCPBench 36a51a1065dda49c1e503b87edf33a1e0b331a74\n"
        "MCPToolBenchPP 2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037\n",
        encoding="utf-8",
    )
    (live_root / "all_annotations.json").write_text("[]\n", encoding="utf-8")

    live_tools = []
    server_tools = {}
    server_categories = {}
    for i in range(525):
        server_index = i % 69
        server = f"live-s{server_index:02d}"
        category = f"LiveCategory{server_index % 8}"
        server_categories[server] = category
        name = f"live-tool-{i:03d}"
        annotations = None if server_index < 7 else ({"readOnlyHint": True} if i % 3 == 0 else None)
        row = {
            "name": name,
            "description": f"Synthetic definition for {name}",
            "inputSchema": {
                "type": "object",
                "properties": {"item_id": {"type": "string"}},
                "required": ["item_id"],
            },
            "outputSchema": None,
            "annotations": annotations,
        }
        live_tools.append((server, row))
        server_tools.setdefault(server, []).append(row)

    # 43 source definitions overlap on seven LiveMCPTool servers.
    overlap = [(srv, row) for srv, row in live_tools if int(srv[-2:]) < 7][:43]
    assert len(overlap) == 43
    live_by_server = {}
    for server, rows in server_tools.items():
        cat = server_categories[server]
        live_by_server.setdefault(cat, {})[server] = {"tools": rows}
    live_doc = [{"category": cat, "tools": servers} for cat, servers in sorted(live_by_server.items())]
    (live_root / "tools.json").write_text(json.dumps(live_doc), encoding="utf-8")

    pp_servers = [f"live-s{i:02d}" for i in range(7)] + ["pp-srv-0", "pp-srv-1", "pp-srv-2"]
    pp_categories = ["browser", "file_system", "finance", "map", "pay", "search"]
    pp_rows = []
    for i, (server, tool) in enumerate(overlap):
        pp_rows.append((pp_categories[i % 6], server, tool))
    for i in range(44):
        server = pp_servers[i % len(pp_servers)]
        name = f"pp-new-tool-{i:02d}"
        tool = {
            "name": name,
            "description": f"Synthetic definition for {name}",
            "input_schema": {
                "type": "object",
                "properties": {"item_id": {"type": "string"}},
                "required": ["item_id"],
            },
        }
        pp_rows.append((pp_categories[i % 6], server, tool))
    assert len(pp_rows) == 87

    by_category = {cat: [] for cat in pp_categories}
    for i, (cat, server, tool) in enumerate(pp_rows):
        by_category[cat].append({
            "uuid": f"synthetic-task-{i:03d}",
            "query": f"synthetic request {i}",
            "mcp_tools_dict": {server: [tool["name"]]},
            "tools": [{
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema") or tool.get("inputSchema") or {},
            }],
            "function_call_label": [],
        })
    for cat, rows in by_category.items():
        (pp_root / f"{cat}.json").write_text(json.dumps(rows), encoding="utf-8")
    (live_root / "LICENSE").write_text("synthetic test fixture\n", encoding="utf-8")
    (pp_root / "LICENSE").write_text("synthetic test fixture\n", encoding="utf-8")

    # The production runner copies the original protocol manifest schema.
    schema_dir = root / "docs" / "experiment_design"
    schema_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs" / "experiment_design" / "run_manifest.schema.json",
                 schema_dir / "run_manifest.schema.json")
    processed = root / "data" / "processed"
    processed.mkdir(parents=True)


def test_protocol_e1_runs_all_three_views_and_emits_schema_valid_failed_manifest(tmp_path):
    _write_synthetic_source_tree(tmp_path)
    out = E1.run_e1(tmp_path, tmp_path / "runs", run_id="E1-synthetic-test")
    manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))

    schema = json.loads((tmp_path / "docs" / "experiment_design" / "run_manifest.schema.json").read_text())
    validate(manifest, schema)

    assert manifest["status"] == "failed"
    assert manifest["experiment_id"] == "E1"
    assert summary["server_categories"]["observed"] == 14
    assert [x["tool_count"] for x in summary["datasets"]] == [525, 87, 569]
    assert [x["server_count"] for x in summary["datasets"]] == [69, 10, 76]
    assert summary["reference_labels"]["status"] == "blocked_missing_independent_reference_labels"
    assert all(x["reference_labels"]["non_read_only_share"] is None for x in summary["datasets"])
    assert summary["definition_hash_validation"]["mismatch_count"] == 0
    assert (out / "registry_category_stacked.png").is_file()
    assert (out / "inputs" / "data" / "processed" / "registry_merged.json").is_file()
    assert (out / "reference_effect_annotator_A.csv").is_file()
    assert (out / "reference_effect_annotator_B.csv").is_file()
    assert (out / "E1_run.zip").is_file()

    with (out / "registry_summary.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [row["tools"] for row in rows] == ["525", "87", "569"]
    with (out / "reference_label_coverage.csv").open(encoding="utf-8", newline="") as f:
        coverage = list(csv.DictReader(f))
    assert all(row["metric_status"] == "blocked_incomplete_independent_reference_labels" for row in coverage)


def test_reference_labels_reject_model_generated_or_incomplete_claims():
    bad = {
        "schema_version": "1.0.0",
        "label_source": "silver_llm",
        "independent_of_silver_labels": False,
        "generated_by_model": True,
        "labels": [{"tool_id": "srv::t", "definition_hash": "0" * 64, "non_read_only": True}],
    }
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "labels.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        try:
            E1.load_reference_labels(path)
        except ValueError:
            pass
        else:
            raise AssertionError("Model-generated labels must never be accepted as reference")
