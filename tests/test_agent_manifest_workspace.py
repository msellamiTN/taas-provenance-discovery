from pathlib import Path

PAGE = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


def test_agent_manifest_workspace_exposes_contract_and_truthful_lifecycle():
    html = PAGE.read_text(encoding="utf-8")
    for marker in (
        'id="agent-manifest-panel"',
        'id="agent-manifest-json"',
        'id="agent-manifest-validate"',
        'id="agent-manifest-reset"',
        'id="agent-manifest-status"',
        'id="agent-manifest-result"',
        "taas.ai/v1alpha1",
        "/api/v1/agents/validate",
        "not saved, authorized or executable",
        "Structural validation only",
    ):
        assert marker in html


def test_agent_manifest_workspace_does_not_expose_fake_publish_or_run_actions():
    html = PAGE.read_text(encoding="utf-8")
    start = html.index('id="agent-manifest-panel"')
    end = html.index("</section>", start)
    panel = html[start:end]
    assert "Publish agent" not in panel
    assert "Run agent" not in panel
    assert "Save agent" not in panel
