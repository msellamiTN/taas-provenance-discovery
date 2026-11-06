from pathlib import Path


STUDIO_HTML = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


def test_agent_engineering_workspace_is_navigable_and_accessible():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'href="#agent-engineering-workspace"' in html
    assert 'id="agent-engineering-workspace"' in html
    assert 'aria-labelledby="agent-engineering-title"' in html
    assert 'id="agent-engineering-status" class="agent-trace-state" role="status" aria-live="polite"' in html


def test_agent_engineering_workspace_uses_authenticated_core_prepare_endpoint():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'fetch("/api/v1/objectives/prepare"' in html
    assert '"Authorization":"Bearer "+token' in html
    assert '"Content-Type":"application/json"' in html
    assert 'provider:$("agent-engineering-provider").value' in html


def test_agent_engineering_workspace_renders_core_records_as_text():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'strong.textContent=' in html
    assert 'td.textContent=String(value??"—")' in html
    assert 'agentEngineeringRaw.textContent=JSON.stringify(data,null,2)' in html
    assert 'innerHTML' not in html[html.index('Agent Engineering Workspace:'):html.index('// The overview is explicitly refreshed')]


def test_agent_engineering_workspace_preserves_lexical_and_structural_limits():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'lexical phrase matches within objective clause spans' in html
    assert 'not semantic proof' in html
    assert 'semantic correctness verified: '+ '"+String(trace.semantic_correctness_verified===true)' in html
    assert 'does not publish an Agent, start discovery, request authorization, or execute tools' in html


def test_agent_engineering_workspace_has_explicit_empty_error_and_clear_states():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'No Objective has been prepared in this workspace.' in html
    assert 'Objective preparation failed:' in html
    assert 'Workspace cleared. No API request was made.' in html
    assert 'No outcome provenance was returned.' in html
