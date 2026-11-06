from pathlib import Path

ROOT = Path(__file__).parents[1]
HTML = ROOT / "src" / "taas" / "studio" / "static" / "index.html"


def test_discovery_history_and_audit_workspace_is_navigable():
    html = HTML.read_text(encoding="utf-8")
    assert 'href="#discovery-observability"' in html
    assert 'id="discovery-observability"' in html
    assert 'id="obs-refresh-runs"' in html
    assert 'id="obs-load-run"' in html
    assert 'id="obs-refresh-audit"' in html
    assert 'id="obs-verify-audit"' in html


def test_workspace_consumes_core_persisted_run_and_audit_endpoints():
    html = HTML.read_text(encoding="utf-8")
    assert 'apiGet("/api/v1/discovery/runs?limit=50")' in html
    assert '"/api/v1/discovery/runs/"+encodeURIComponent(id)' in html
    assert 'apiGet("/api/v1/audit/events?limit=100")' in html
    assert 'apiGet("/api/v1/audit/verify")' in html


def test_audit_integrity_displays_core_divergence_without_claiming_execution():
    html = HTML.read_text(encoding="utf-8")
    assert 'data.chain_valid===true' in html
    assert 'data.first_divergence' in html
    assert "not truth of event claims or execution proof" in html
    assert "not proof of tool invocation, task completion, authorization, or governed execution" in html


def test_workspace_renders_core_records_as_text_not_html():
    html = HTML.read_text(encoding="utf-8")
    start = html.index("// UX-F02: read-only discovery history and audit integrity workspace.")
    end = html.index("// Restore the last successful Core response after a page refresh.", start)
    code = html[start:end]
    assert "textContent" in code
    assert "innerHTML" not in code


def test_duplicate_record_ids_and_unknown_fields_are_tolerated():
    html = HTML.read_text(encoding="utf-8")
    assert 'record.run_id || record.discovery_run_id || record.event_id || record.id' in html
    assert 'Array.isArray(data.events)?data.events:[]' in html
    assert 'Array.isArray(data.runs)?data.runs:(Array.isArray(data.records)?data.records:[])' in html


def test_safety_notice_reflects_persisted_history_but_keeps_execution_disabled():
    html = HTML.read_text(encoding="utf-8")
    assert "persisted discovery history and audit inspection are read-only pre-execution observations" in html
    assert "Governed MCP execution and isolated workers are not enabled" in html
