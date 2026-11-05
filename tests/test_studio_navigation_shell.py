from pathlib import Path
import re


STUDIO_HTML = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


def test_every_studio_navigation_link_has_a_target():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    links = re.findall(r'<a href="#([^"]+)"', html)
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    assert links, "Studio navigation must expose workspace links"
    assert len(links) == len(set(links)), "Navigation destinations must be unique"
    assert set(links) <= ids, f"Missing navigation targets: {sorted(set(links) - ids)}"


def test_agent_studio_is_inside_the_persistent_workspace_shell():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    agent = html.index('id="agent-studio"')
    shell_close = html.index("</div>\n  </div>\n\n</main>", agent)
    assert agent < shell_close, "Agent Studio must remain inside the persistent navigation shell"


def test_navigation_uses_single_workspace_visibility_and_keeps_host_snapshot():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'document.querySelector(".studio-content")' in html
    assert "showStudioWorkspace" in html
    assert 'child.id === "runtime-overview"' in html
    assert 'else if (child !== root) hideForNavigation(child);' in html
    assert 'node.hidden = true;' in html
    assert 'node.dataset.studioNavHidden = "true";' in html
    assert 'restoreNavigationVisibility();' in html


def test_model_and_agent_workspaces_have_distinct_navigation_targets():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    for target in ("model-runtime-panel", "agent-chat-panel", "agent-goal-panel"):
        assert f'href="#{target}"' in html
        assert f'id="{target}"' in html


def test_workspace_context_bar_tracks_the_active_navigation_destination():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'id="studio-workspace-context-title"' in html
    assert 'aria-live="polite"' in html
    assert 'workspaceContextTitle.textContent = link.textContent' in html
    assert 'class="workspace-context"' in html


def test_workspace_context_bar_is_responsive_and_respects_reduced_motion():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert ".workspace-context" in html
    assert "@media(max-width:560px)" in html
    assert "@media(prefers-reduced-motion:reduce)" in html


def test_platform_overview_uses_live_core_resource_endpoints():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    for endpoint in (
        "/api/v1/agents?limit=100",
        "/api/v1/skills?limit=100",
        "/api/v1/bench/tools?source=all&limit=1&offset=0",
        "/api/v1/mcp/servers",
    ):
        assert f'apiGet("{endpoint}")' in html
    assert "Promise.allSettled" in html
    assert "data.total" in html
    assert "data.count" in html


def test_platform_overview_distinguishes_empty_partial_and_unavailable_data():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'status.textContent="Partial data' in html
    assert 'status.textContent="Overview unavailable' in html
    assert 'emptyMessage||("No "+kind+" versions' in html
    assert 'Agent registry unavailable:' in html
    assert 'Skill registry unavailable:' in html


def test_platform_overview_preserves_lifecycle_states_and_avoids_execution_claims():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'record.lifecycle_state||"state unavailable"' in html
    assert 'record.revoked===true?"revoked"' in html
    assert "Read-only overview · no execution" in html
    assert 'id="overview-dashboard-refresh"' in html


def test_platform_overview_has_responsive_resource_and_metric_layouts():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert ".overview-metrics" in html
    assert ".overview-resource-grid" in html
    assert "@media(max-width:900px){.overview-metrics" in html
    assert "@media(max-width:620px){.overview-resource-grid" in html
