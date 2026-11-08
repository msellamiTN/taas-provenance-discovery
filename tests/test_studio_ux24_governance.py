from pathlib import Path
import re
import shutil
import subprocess

import pytest

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


def test_ux24_labels_audit_verification_as_scanned_prefix_only():
    html = HTML.read_text(encoding="utf-8")
    ledger = (ROOT / "src" / "taas" / "studio" / "audit_ledger.py").read_text(encoding="utf-8")
    assert "first 1,000 events" in html
    assert "SCANNED_PREFIX_VALID" in html
    assert "SCANNED_PREFIX_INVALID_OR_UNKNOWN" in html
    assert "events = list_events(limit=1000)" in ledger
    assert '"chain_valid": first_divergence is None' in ledger


def test_ux24_clears_stale_subject_data_and_does_not_overstate_empty_evidence():
    html = HTML.read_text(encoding="utf-8")
    assert "const resetAssessment=()" in html
    assert "agentSelect.disabled=true;versionSelect.disabled=true" in html
    assert "NO_VERIFIED_RECORDS" in html
    assert 'verified>0?"VERIFIED_RECORDS_PRESENT":"NO_VERIFIED_RECORDS"' in html


def test_studio_inline_javascript_parses_with_node(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable; browser/runtime acceptance remains separate.")
    html = HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script\\b[^>]*>(.*?)</script>", html, flags=re.DOTALL)
    assert scripts, "Studio page must contain its application script."
    for index, script in enumerate(scripts):
        source = tmp_path / f"studio-{index}.js"
        source.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, "--check", str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
