from pathlib import Path


def _studio_html() -> str:
    return (Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html").read_text(encoding="utf-8")


def _ux7_script(html: str) -> str:
    start = html.index("// UX-7: accessible local tabs")
    end = html.index("// UX-6: compare two user-selected", start)
    return html[start:end]


def test_ux7_navigation_and_workspace_are_present():
    html = _studio_html()
    assert 'href="#runtime-observability"' in html
    assert 'id="runtime-observability"' in html
    assert 'id="ux7-title"' in html


def test_ux7_uses_honest_unconfigured_and_empty_states():
    html = _studio_html()
    for marker in (
        "No runtime adapter or isolated worker is configured",
        "Not configured",
        "Not reported",
        "No execution sessions",
        "No runtime event timeline",
        "No runtime logs",
        "No distributed traces",
        "No runtime metrics",
        "Runtime diagnostics unavailable",
    ):
        assert marker in html


def test_ux7_execution_and_export_controls_are_disabled():
    html = _studio_html()
    assert 'id="runtime-observability"' in html
    section = html.split('id="runtime-observability"', 1)[1].split('<section id="runtime"', 1)[0]
    assert 'Run execution · unavailable</button>' in section
    assert 'disabled aria-disabled="true"' in section
    assert 'button type="button" class="secondary" disabled>Export session' in section


def test_ux7_does_not_fabricate_operational_evidence_or_overclaim():
    html = _studio_html()
    for marker in (
        "No events have been synthesized",
        "Trace identifiers and spans are not fabricated",
        "Observability is not authorization",
        "not proof of semantic correctness or goal fulfilment",
        "Discovery metadata and assurance evidence are not execution records",
        "Authorization</dt><dd>Not granted",
        "Execution state</dt><dd>Disabled",
    ):
        assert marker in html


def test_ux7_tabs_are_accessible_and_keyboard_operable():
    html = _studio_html()
    for marker in (
        'role="tablist"',
        'role="tab"',
        'role="tabpanel"',
        'aria-controls="ux7-view-sessions"',
        'aria-selected="true"',
        "event.key==='ArrowRight'",
        "event.key==='ArrowLeft'",
        "event.key==='Home'",
        "event.key==='End'",
        "tabIndex=active?0:-1",
    ):
        assert marker in html


def test_ux7_script_is_local_only_and_has_no_execution_or_runtime_calls():
    script = _ux7_script(_studio_html())
    for forbidden in ("fetch(", "apiGet(", "apiPost(", "runtimePost(", "tools/call", "execute(", "WebSocket("):
        assert forbidden not in script
    assert "addEventListener('click'" in script
    assert "aria-selected" in script


def test_ux7_is_documented_as_ui_only_and_acceptance_pending():
    doc = (Path(__file__).parents[1] / "docs" / "studio" / "UX_7_ISOLATED_RUNTIME_OBSERVABILITY.md").read_text(encoding="utf-8")
    assert "does not implement a runtime" in doc
    assert "Execution: disabled" in doc
    assert "Acceptance still required" in doc
