from pathlib import Path

ROOT = Path(__file__).parents[1]
HTML = ROOT / "src" / "taas" / "studio" / "static" / "index.html"
API = ROOT / "src" / "taas" / "studio" / "api.py"
POLICY = ROOT / "src" / "taas" / "studio" / "policy_engine.py"


def test_ux24_workspace_navigation_and_all_views_are_present():
    html = HTML.read_text(encoding="utf-8")
    for marker in (
        'href="#agent-governance-trust-center"',
        'id="agent-governance-trust-center"',
        'id="ux24-panel-overview"',
        'id="ux24-panel-policy"',
        'id="ux24-panel-consistency"',
        'id="ux24-panel-access"',
        'id="ux24-panel-evidence"',
    ):
        assert marker in html


def test_ux24_uses_existing_core_read_endpoints_only():
    html = HTML.read_text(encoding="utf-8")
    for endpoint in (
        "/api/v1/agents?limit=500",
        "/release-readiness",
        "/policy-verdict",
        "/approvals",
        "/api/v1/agents/events",
        "/api/v1/audit/verify",
    ):
        assert endpoint in html
    assert "/api/v1/policy/evaluate" not in html
    assert "/api/v1/mcp/" not in html[html.index("// UX-24:"):]


def test_ux24_preserves_non_authoritative_governance_semantics():
    html = HTML.read_text(encoding="utf-8")
    for phrase in (
        "diagnostic only",
        "does not approve",
        "authorization_granted=false",
        "No authorization preflight was run",
        "UNKNOWN",
    ):
        assert phrase in html


def test_ux24_policy_verdict_remains_non_authorizing_in_core():
    api = API.read_text(encoding="utf-8")
    policy = POLICY.read_text(encoding="utf-8")
    assert '"/api/v1/agents/{agent_id}/versions/{version}/policy-verdict"' in api
    assert '"authorization_granted": False' in policy
    assert '"execution_enabled": False' in policy
