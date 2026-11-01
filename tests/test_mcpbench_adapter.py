from taas.mcpbench import raw_tools_from_mcpbench


def test_raw_tools_from_mcpbench_preserves_identity_and_schema():
    tool_map = {
        "GitHub:search_repositories": {
            "server": "GitHub",
            "original_name": "search_repositories",
            "description": "Search repositories",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "annotations": {"readOnlyHint": True},
        }
    }
    raw, key_by_id = raw_tools_from_mcpbench(tool_map)
    assert len(raw) == 1
    assert raw[0].id == "GitHub::search_repositories"
    assert raw[0].input_schema["required"] == ["query"]
    assert raw[0].annotations == {"readOnlyHint": True}
    assert key_by_id["GitHub::search_repositories"] == "GitHub:search_repositories"


def test_raw_tools_from_mcpbench_supports_alternate_field_names():
    tool_map = {
        "Weather:forecast": {
            "name": "forecast",
            "description": "Get forecast",
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object"},
        }
    }
    raw, key_by_id = raw_tools_from_mcpbench(tool_map)
    assert raw[0].server == "Weather"
    assert raw[0].name == "forecast"
    assert raw[0].output_schema == {"type": "object"}
    assert key_by_id["Weather::forecast"] == "Weather:forecast"


def test_duplicate_mcp_tool_identity_is_rejected():
    tool_map = {
        "Server:tool-a": {"server": "Server", "original_name": "tool"},
        "Server:tool-b": {"server": "Server", "original_name": "tool"},
    }
    try:
        raw_tools_from_mcpbench(tool_map)
    except ValueError as exc:
        assert "Duplicate MCP tool identity" in str(exc)
    else:
        raise AssertionError("duplicate identity must fail closed")
