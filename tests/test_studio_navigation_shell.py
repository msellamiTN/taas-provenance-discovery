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
    assert "child.hidden = child !== root" in html


def test_model_and_agent_workspaces_have_distinct_navigation_targets():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    for target in ("model-runtime-panel", "agent-chat-panel", "agent-goal-panel"):
        assert f'href="#{target}"' in html
        assert f'id="{target}"' in html
