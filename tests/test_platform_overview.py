from pathlib import Path
import re


ROOT = Path(__file__).parents[1]
HTML = ROOT / "src" / "taas" / "studio" / "static" / "index.html"
API = ROOT / "src" / "taas" / "studio" / "api.py"


def test_platform_overview_has_all_inventory_targets_and_accessible_status():
    html = HTML.read_text(encoding="utf-8")
    for element_id in (
        "platform-overview",
        "platform-overview-status",
        "platform-overview-refresh",
        "overview-agents-value",
        "overview-skills-value",
        "overview-tools-value",
        "overview-mcp-value",
        "overview-datasets-value",
        "overview-recent-agents",
        "overview-recent-skills",
    ):
        assert f'id="{element_id}"' in html
    assert 'id="platform-overview-status" class="platform-overview-status" role="status" aria-live="polite"' in html


def test_platform_overview_uses_existing_authenticated_core_endpoints():
    html = HTML.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    endpoints = (
        "/api/v1/agents?limit=100",
        "/api/v1/skills?limit=100",
        "/api/v1/bench/tools?source=all&limit=1&offset=0",
        "/api/v1/mcp/servers",
        "/api/v1/bench/datasets",
    )
    for endpoint in endpoints:
        assert endpoint in html
        route = endpoint.split("?")[0]
        assert route in api


def test_platform_overview_handles_partial_failures_without_fabricating_counts():
    html = HTML.read_text(encoding="utf-8")
    start = html.index("const refreshPlatformOverview = async () =>")
    end = html.index('overviewRefresh.addEventListener("click",refreshPlatformOverview);', start)
    implementation = html[start:end]
    assert "Promise.allSettled" in implementation
    assert 'setOverviewMetric(key,null' in implementation
    assert 'byKey.tools.total' in implementation
    assert 'byKey.mcp.count' in implementation
    assert "innerHTML" not in implementation
    assert "textContent" in implementation


def test_platform_overview_does_not_claim_model_inventory_or_operational_readiness():
    html = HTML.read_text(encoding="utf-8")
    assert "Model inventory is intentionally not counted here" in html
    assert "not live connectivity" in html
    assert "not readiness, authorization or execution" in html
    assert "No discovery, model loading, policy decision, authorization or execution" in html


def test_platform_overview_ids_are_unique():
    html = HTML.read_text(encoding="utf-8")
    ids = re.findall(r'\\bid="([^"]+)"', html)
    overview_ids = [value for value in ids if value.startswith("platform-overview") or value.startswith("overview-")]
    assert len(overview_ids) == len(set(overview_ids))
