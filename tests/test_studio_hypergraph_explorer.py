from pathlib import Path


STUDIO_HTML = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


def test_hypergraph_explorer_is_reachable_from_studio_navigation():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert '<a href="#hypergraph-explorer">Hypergraph explorer</a>' in html
    assert 'id="hypergraph-explorer"' in html


def test_hypergraph_explorer_consumes_api_projection_without_synthesizing_one():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'renderHypergraphProjection(data.hypergraph_projection_status === "available" ? data.hypergraph_projection : null)' in html
    assert 'projection.schema==="taas.hypergraph-projection/v1"' in html
    assert 'No graph was synthesized' in html


def test_hypergraph_explorer_displays_core_owned_reachability_and_provenance_fields():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    for field in ("reachable", "information_label", "derivation", "fired_in_reachability", "contract_fingerprint", "forbidden_with"):
        assert field in html
    assert "Core reported" in html
    assert "Core derivation" in html


def test_hypergraph_explorer_has_keyboard_accessible_graph_entities_and_list_fallback():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'tabindex:"0"' in html
    assert 'role:"button"' in html
    assert 'id="hg-entity-list"' in html
    assert 'addEventListener("keydown"' in html


def test_hypergraph_explorer_does_not_implement_semantic_reachability_or_execute_tools():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert "never derives reachability" in html
    assert "No MCP calls or execution performed" in html
    assert "fired_in_reachability" in html
