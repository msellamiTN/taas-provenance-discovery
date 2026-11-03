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
        "published configuration",
        "not saved, authorized or executable",
        "structurally validated",
        'id="agent-manifest-save"',
        'id="agent-manifest-validate-saved"',
        'id="agent-manifest-publish"',
        "/api/v1/agents/",
        'id="agent-registry-snapshot-refresh"',
        'id="agent-registry-snapshot-inspect"',
        'id="agent-registry-snapshot-select"',
        "/api/v1/mcp/registry/snapshots/inspect",
        "tools/list only",
        "registry_snapshot_id",
        "Save immutable draft",
        "Publish version",
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


def test_agent_manifest_workspace_uses_persisted_lifecycle_actions_not_fake_execution():
    html = PAGE.read_text(encoding="utf-8")
    panel_start = html.index('id="agent-manifest-panel"')
    panel_end = html.index("</section>", panel_start)
    panel = html[panel_start:panel_end]
    assert "Save immutable draft" in panel
    assert "Validate saved version" in panel
    assert "Publish version" in panel
    assert "Run agent" not in panel
    assert "Invoke tools" not in panel
    assert "execution remains disabled" in html

def test_agent_manifest_workspace_supports_versioned_mcp_snapshot_binding():
    html = PAGE.read_text(encoding="utf-8")
    assert "Load stored MCP snapshots" in html
    assert "Inspect configured MCP servers" in html
    assert "No MCP snapshot selected" in html
    assert '"/publish"' in html
    assert "MCP schema snapshots are created through read-only tools/list inspection" in html
