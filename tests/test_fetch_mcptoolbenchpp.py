import json
import pytest
from scripts.fetch_mcptoolbenchpp import CATEGORIES, validate_snapshot


def _valid_row():
    return {
        "uuid": "q1", "query": "find a record",
        "mcp_tools_dict": {"server-a": ["search"]},
        "tools": [{"name": "search", "description": "Search records"}],
        "function_call_label": [{"name": "search", "mcp_server": "server-a"}],
    }


def test_snapshot_validator_rejects_wrong_pinned_cardinalities(tmp_path):
    files = {}
    for category in CATEGORIES:
        path = tmp_path / f"{category}.json"
        path.write_text(json.dumps([_valid_row()]), encoding="utf-8")
        files[category] = path
    with pytest.raises(ValueError, match="cardinality sentinel mismatch"):
        validate_snapshot(files)


def test_snapshot_validator_rejects_malformed_source_rows(tmp_path):
    files = {}
    for category in CATEGORIES:
        path = tmp_path / f"{category}.json"
        path.write_text(json.dumps([{"uuid": "q1"}]), encoding="utf-8")
        files[category] = path
    with pytest.raises(ValueError, match="missing required fields"):
        validate_snapshot(files)
