from pathlib import Path

STUDIO_HTML = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


def test_model_runtime_agent_chat_and_agent_design_are_independent_workspaces():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    for target in ("model-runtime-panel", "agent-chat-panel", "agent-goal-panel"):
        assert f'href="#{target}"' in html
        assert f'id="{target}"' in html
    assert "isolate the selected nested panel at each level" in html
    assert "sibling.hidden = true" in html
    assert "branch.hidden = false" in html


def test_model_and_agent_workspaces_use_consistent_single_column_task_layouts():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert "#agent-studio>.grid{grid-template-columns:minmax(0,1fr)!important}" in html
    assert "#model-runtime-panel,#agent-chat-panel,#agent-goal-panel" in html
    assert "max-height:420px;min-height:180px" in html


def test_nested_workspace_switching_preserves_global_runtime_snapshot():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'if (child.id === "runtime-overview") child.hidden = false;' in html
    assert "else child.hidden = child !== root;" in html
