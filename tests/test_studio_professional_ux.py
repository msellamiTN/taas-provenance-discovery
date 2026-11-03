from pathlib import Path

STUDIO_HTML = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


def test_professional_design_tokens_and_surface_hierarchy_are_present():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    for token in ("--ink:", "--muted:", "--line:", "--surface:", "--canvas:", "--blue:"):
        assert token in html
    assert ".studio-nav" in html
    assert ".studio-content" in html
    assert "box-shadow:var(--shadow)" in html


def test_studio_controls_have_visible_focus_and_reduced_motion_support():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert "button:focus-visible" in html
    assert "input:focus" in html
    assert "prefers-reduced-motion:reduce" in html
    assert "@media(max-width:560px)" in html


def test_visual_refresh_does_not_claim_execution_capability():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert "Execution disabled" in html
    assert "does not invoke MCP tools" in html
