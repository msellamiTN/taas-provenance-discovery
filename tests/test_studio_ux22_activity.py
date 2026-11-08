"""Contract and safety tests for UX-22 recorded Agent-version activity."""
from pathlib import Path

ROOT = Path(__file__).parents[1]
HTML = ROOT / "src" / "taas" / "studio" / "static" / "index.html"


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def _ux22() -> str:
    html = _html()
    start = html.index('<section id="ux22-agent-observability"')
    end = html.index('<section id="ux23-discovery-composition"', start)
    return html[start:end]


def _ux22_script() -> str:
    html = _html()
    start = html.index("// UX-22: exact-version recorded governance activity")
    end = html.index("// UX-21:", start)
    return html[start:end]


def test_ux22_renders_approved_recorded_activity_workspace():
    section = _ux22()
    for element_id in (
        "ux22-agent-id", "ux22-version", "ux22-lifecycle-count",
        "ux22-verdict-count", "ux22-approval-count", "ux22-timeline",
        "ux22-governance-rows", "ux22-config-rows", "ux22-unsupported",
        "ux22-authorization", "ux22-execution",
    ):
        assert f'id="{element_id}"' in section


def test_ux22_does_not_reintroduce_performance_charts_or_claims():
    section = _ux22().lower()
    assert "<svg" not in section
    assert "<canvas" not in section
    assert "latency" in section and "cost" in section
    assert "performance telemetry unavailable" in section
    assert "health score" not in section


def test_ux22_demo_is_explicitly_synthetic_and_makes_no_api_call():
    script = _ux22_script()
    demo = script[script.index("const demo=()=>"):script.index("const live=async()=>")]
    assert "DEMO DATA ONLY" in demo
    assert "no API request was made" in demo
    assert "fetch(" not in demo


def test_ux22_live_request_is_authenticated_and_exact_version_scoped():
    script = _ux22_script()
    assert '"/api/v1/agents/"+encodeURIComponent(agent)+"/versions/"+encodeURIComponent(version)+"/activity"' in script
    assert '"Authorization":"Bearer "+token' in script
    assert 'data.agent_id!==agent' in script
    assert 'data.version!==version' in script
    assert 'data.schema!=="taas.agent-version-activity/v1"' in script


def test_ux22_preserves_unknown_and_unavailable_instead_of_synthesizing_zero():
    script = _ux22_script()
    assert 'put("ux22-lifecycle-count","UNAVAILABLE")' in script
    assert 'put("ux22-authorization","UNKNOWN")' in script
    assert 'put("ux22-execution","UNKNOWN")' in script
    assert "No demo fallback" in script
    assert "Source unavailable; no zero inferred." in script


def test_ux22_matches_nested_approval_audit_and_latest_event_contract():
    script = _ux22_script()
    assert "auditApproval=approval.audit_approval_events||{}" in script
    assert "const event=block?.state===" in script
    assert "block.latest" in script
    assert "full event history is not implied" in script


def test_ux22_keeps_configuration_distinct_from_usage_and_execution():
    section = _ux22()
    assert "Manifest-derived configuration only" in section
    assert "do not demonstrate tool usage" in section
    script = _ux22_script()
    assert 'payload.authorization_granted===false' in script
    assert 'payload.execution_performed===false' in script
