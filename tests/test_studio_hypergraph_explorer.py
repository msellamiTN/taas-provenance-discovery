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


def test_live_studio_api_projects_real_core_discovery(monkeypatch):
    """Exercise the authenticated Studio route with the real DiscoveryEngine.

    The tool is a local synthetic contract. No MCP server is contacted or invoked.
    """
    from fastapi.testclient import TestClient

    from taas.studio.api import app

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "colab-local-test-token")
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    assert 'id="hypergraph-explorer"' in home.text
    assert 'id="hg-canvas"' in home.text

    payload = {
        "goal_spec": {
            "prompt": "List orders for a customer",
            "prompt_inputs": ["identifier"],
            "goals": [{
                "id": "list_orders_goal",
                "class": "retrieve",
                "in": ["identifier"],
                "out": "record[]",
                "eff": ["read(*)"],
                "sigma": "data",
                "deps": [],
                "desc": "Retrieve the customer's orders",
            }],
        },
        "tools": [{
            "server": "colab-local",
            "name": "list_orders",
            "description": "List customer orders",
            "input_schema": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
            "output_schema": {
                "type": "array",
                "items": {"type": "object"},
            },
            "annotations": {"readOnlyHint": True},
            "source": "colab-synthetic-fixture",
        }],
    }

    unauthenticated = client.post("/api/v1/discover", json=payload)
    assert unauthenticated.status_code == 401

    response = client.post(
        "/api/v1/discover",
        headers={"Authorization": "Bearer colab-local-test-token"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["execution_performed"] is False
    assert result["status"] == "selected", result
    assert result["hypergraph_projection_status"] == "available", result
    projection = result["hypergraph_projection"]
    assert projection["schema"] == "taas.hypergraph-projection/v1"
    assert projection["vertices"]
    tool_edge = next(
        edge for edge in projection["hyperedges"]
        if edge.get("kind") == "tool" and edge.get("name") == "list_orders"
    )
    assert tool_edge["fired_in_reachability"] is True
    assert any(
        vertex["semantic_type"] == "record[]" and vertex["reachable"] is True
        for vertex in projection["vertices"]
    )


def test_hypergraph_explorer_actions_reuse_existing_discovery_and_goal_editor():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'id="hg-run-discovery"' in html
    assert 'id="hg-edit-goal"' in html
    assert 'const hgRun = $("hg-run-discovery");' in html
    assert 'hgRun.addEventListener("click", () => run.click());' in html
    assert 'const setDiscoveryStatus = (message) =>' in html
    assert '$("status").textContent = message;' in html
    assert '$("hg-status").textContent = message;' in html
    assert 'item.getAttribute("href") === "#goal-editor"' in html



def test_last_discovery_result_is_restored_after_refresh_without_persisting_authentication():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'const DISCOVERY_RESULT_STORAGE_KEY = "taas.studio.discovery-result.v1";' in html
    assert "sessionStorage.setItem(DISCOVERY_RESULT_STORAGE_KEY, serialized)" in html
    assert "sessionStorage.getItem(DISCOVERY_RESULT_STORAGE_KEY)" in html
    assert "renderDiscoveryResult(data, snapshot.context || {})" in html
    assert "restoreLastDiscoveryResult();" in html
    assert "persistDiscoveryResult(data, {benchmarkTaskNotEvaluated})" in html
    assert "TAAS_STUDIO_API_TOKEN" not in html[html.index("const persistDiscoveryResult"):html.index("const restoreLastDiscoveryResult")]
    assert "localStorage.setItem" not in html
