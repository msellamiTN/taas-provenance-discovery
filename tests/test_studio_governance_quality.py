from pathlib import Path


def _studio_html() -> str:
    return (Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html").read_text(encoding="utf-8")


def _ux8_script(html: str) -> str:
    start = html.index("// UX-8: local accessible tabs only")
    end = html.index("// UX-7: accessible local tabs", start)
    return html[start:end]


def test_ux8_navigation_and_six_panels_are_present():
    html = _studio_html()
    assert 'href="#platform-governance-quality"' in html
    assert 'id="platform-governance-quality"' in html
    for panel in ("overview", "accessibility", "security", "performance", "validation", "reports"):
        assert f'id="ux8-panel-{panel}"' in html


def test_ux8_uses_evidence_states_and_does_not_claim_conformance():
    html = _studio_html()
    for marker in ("NOT_RUN", "UNKNOWN", "WCAG 2.2 AA is the target", "not a certification"):
        assert marker in html


def test_ux8_does_not_fabricate_scores_metrics_or_validation_runs():
    html = _studio_html()
    for forbidden in ("92%", "24/24 passed", "LCP 1.2 s", "INP 68 ms", "CLS 0.01", "Validation run #"):
        assert forbidden not in html


def test_ux8_validation_and_security_states_are_explicitly_unrun_or_unknown():
    html = _studio_html()
    for marker in ("Build / packaging", "Unit / regression tests", "Browser smoke / interaction",
                   "Secret handling and redaction", "Authentication and RBAC",
                   "Worker isolation and network policy", "NO REPORT RECORDED"):
        assert marker in html


def test_ux8_tabs_are_accessible_and_keyboard_operable():
    html = _studio_html()
    for marker in ('role="tablist"', 'role="tab"', 'role="tabpanel"',
                   'aria-controls="ux8-panel-overview"', 'aria-selected="true"',
                   "event.key==='ArrowRight'", "event.key==='ArrowLeft'",
                   "event.key==='Home'", "event.key==='End'"):
        assert marker in html


def test_ux8_script_is_local_only_and_does_not_execute_checks():
    script = _ux8_script(_studio_html())
    for forbidden in ("fetch(", "apiGet(", "apiPost(", "runtimePost(",
                      "tools/call", "execute(", "WebSocket(", "performance.getEntries"):
        assert forbidden not in script
    assert "addEventListener('click'" in script


def test_ux8_documents_governance_and_pending_acceptance():
    doc = (Path(__file__).parents[1] / "docs" / "studio" / "UX_8_PLATFORM_GOVERNANCE_QUALITY.md").read_text(encoding="utf-8")
    assert "does not imply that an assessment was run" in doc
    assert "Governed MCP execution and isolated workers remain disabled" in doc
    assert "Acceptance still required" in doc
