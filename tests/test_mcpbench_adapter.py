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



def test_selected_catalogue_scope_limits_executor_and_restores_evaluator_catalogue():
    from types import SimpleNamespace
    from taas.mcpbench import selected_tool_catalogue_scope

    full = {
        "GitHub:search": {"server": "GitHub", "name": "search"},
        "GitHub:delete": {"server": "GitHub", "name": "delete"},
    }
    manager = SimpleNamespace(all_tools=full)
    selected = {"GitHub:search": {"untrusted": "metadata"}}

    with selected_tool_catalogue_scope(manager, selected):
        assert list(manager.all_tools) == ["GitHub:search"]
        assert manager.all_tools["GitHub:search"] is full["GitHub:search"]

    assert manager.all_tools is full
    assert set(manager.all_tools) == {"GitHub:search", "GitHub:delete"}


def test_selected_catalogue_scope_restores_after_execution_error():
    from types import SimpleNamespace
    import pytest
    from taas.mcpbench import selected_tool_catalogue_scope

    full = {"S:read": {"server": "S"}}
    manager = SimpleNamespace(all_tools=full)
    with pytest.raises(RuntimeError, match="executor failed"):
        with selected_tool_catalogue_scope(manager, {"S:read": {}}):
            raise RuntimeError("executor failed")
    assert manager.all_tools is full


def test_selected_catalogue_scope_rejects_unknown_keys_without_mutation():
    from types import SimpleNamespace
    import pytest
    from taas.mcpbench import selected_tool_catalogue_scope

    full = {"S:read": {"server": "S"}}
    manager = SimpleNamespace(all_tools=full)
    with pytest.raises(ValueError, match="absent from live catalogue"):
        with selected_tool_catalogue_scope(manager, {"S:delete": {}}):
            pass
    assert manager.all_tools is full


def test_selected_task_executor_scope_preserves_executor_snapshot_and_restores_manager():
    from types import SimpleNamespace
    from taas.mcpbench import selected_task_executor_scope

    full = {
        "S:read": {"server": "S", "name": "read"},
        "S:delete": {"server": "S", "name": "delete"},
    }
    manager = SimpleNamespace(all_tools=full)
    selected = {"S:read": {"ignored": "metadata"}}

    with selected_task_executor_scope(manager, selected) as scoped:
        executor_snapshot = dict(manager.all_tools)
        assert set(executor_snapshot) == {"S:read"}
        assert scoped is manager.all_tools

    assert manager.all_tools is full
    assert set(executor_snapshot) == {"S:read"}
    assert executor_snapshot["S:read"] is full["S:read"]


def test_selected_task_executor_scope_rejects_unknown_tool_and_restores():
    from types import SimpleNamespace
    import pytest
    from taas.mcpbench import selected_task_executor_scope

    full = {"S:read": {"server": "S"}}
    manager = SimpleNamespace(all_tools=full)
    with pytest.raises(ValueError, match="absent from live catalogue"):
        with selected_task_executor_scope(manager, {"S:write": {}}):
            pass
    assert manager.all_tools is full
