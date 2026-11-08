from pathlib import Path

HTML = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


def test_ux9_navigation_and_all_mockup_views_exist():
    html = HTML.read_text(encoding="utf-8")
    assert '<a href="#objective-traceability-explorer">Traceability explorer</a>' in html
    for marker in ('id="ux9-panel-graph"', 'id="ux9-panel-lineage"', 'id="ux9-panel-relationships"',
                   'id="ux9-panel-evidence"', 'id="ux9-panel-export"', 'id="ux9-inspector-body"',
                   'id="ux9-group-objectives"', 'id="ux9-group-subgoals"', 'id="ux9-group-tools"', 'id="ux9-group-evidence"', 'id="ux9-group-experiments"', 'id="ux9-group-other"', 'id="ux9-canvas"'):
        assert marker in html


def test_ux9_calls_existing_authenticated_core_projection_endpoint():
    html = HTML.read_text(encoding="utf-8")
    assert '/api/v1/hypergraph/objective-traceability' in html
    assert 'Authorization":"Bearer "+token' in html
    assert 'data.hypergraph_projection.schema!=="taas.hypergraph-projection/v1"' in html


def test_ux9_does_not_synthesize_relationships_or_claim_execution():
    html = HTML.read_text(encoding="utf-8")
    assert "No graph has been synthesized" in html
    assert "No tools executed; no authorization granted." in html
    assert "does not calculate reachability or semantic compatibility" in html
    assert "No semantic inference, authorization, tool execution" in html


def test_ux9_has_all_filters_and_keyboard_accessible_tabs_and_edges():
    html = HTML.read_text(encoding="utf-8")
    for marker in ('id="ux9-filter-missing"', 'id="ux9-filter-unresolved"',
                   'id="ux9-filter-review"', 'id="ux9-filter-declared"',
                   'line.setAttribute("role","button")', 'inspect("relationship",e)', "ev.key"):
        assert marker in html
    assert "ArrowRight" in html and "ArrowLeft" in html and "Home" in html and "End" in html


def test_ux9_documents_evidence_and_acceptance_boundaries():
    doc = (Path(__file__).parents[1] / "docs" / "studio" / "UX_9_OBJECTIVE_TRACEABILITY_EXPLORER.md").read_text(encoding="utf-8")
    assert "semantic correctness" in doc
    assert "No MCP tools are called or executed" in doc
    assert "Full pytest, repository CI" in doc



def test_ux9_inline_script_parses_when_node_is_available():
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if node is None:
        import pytest
        pytest.skip("Node.js is not installed")
    html = HTML.read_text(encoding="utf-8")
    start = html.index("<script>") + len("<script>")
    end = html.index("</script>", start)
    source_text = html[start:end]
    assert "// UX-9 Objective Traceability Explorer" in source_text
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as source:
        source.write(source_text)
        source.flush()
        result = subprocess.run([node, "--check", source.name], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
