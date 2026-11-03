"""Real-browser acceptance test for the Hypergraph Explorer.

Requires the optional Playwright browser runtime. The test starts the actual
FastAPI Studio on loopback and drives its shipped HTML/JavaScript. Discovery
uses the built-in demo contract as metadata only; it never invokes MCP tools.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
API_TOKEN = "colab-browser-e2e-token"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.browser
def test_hypergraph_explorer_browser_journey(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Exercise auth, real Core discovery, graph interactions and responsive layout."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised in Colab setup
        pytest.skip("Install Playwright and Chromium using the Colab E2E notebook") from exc

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["TAAS_STUDIO_API_TOKEN"] = API_TOKEN
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    server = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "taas.studio.api:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise AssertionError(f"Studio server exited early with code {server.returncode}")
            try:
                with urllib.request.urlopen(base_url + "/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        else:
            raise AssertionError("Studio server did not become healthy within 45 seconds")

        mcp_requests: list[str] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on(
                "request",
                lambda request: mcp_requests.append(request.url)
                if "/api/v1/mcp/" in request.url else None,
            )

            page.goto(base_url, wait_until="networkidle")
            assert page.title() == "TaaS Studio — Tool Intelligence Platform"
            assert page.locator("#hg-empty").is_visible()
            assert page.locator("#hg-filter").is_disabled()

            # Authentication is verified by the real API, not simulated in the browser.
            page.locator("#token").fill(API_TOKEN)
            page.locator("#studio-auth-connect").click()
            page.get_by_text("Connected · token verified for this runtime").wait_for(timeout=15000)

            # The built-in demo contract is metadata only. The real DiscoveryEngine
            # returns the projection; no MCP server or external tool is contacted.
            page.locator("#run").click()
            page.wait_for_function(
                """() => {
                  const status = document.querySelector('#hg-projection-state')?.textContent || '';
                  return status.startsWith('Core projection ·') ||
                         status === 'Projection unavailable' ||
                         status === 'Invalid projection';
                }""",
                timeout=30000,
            )
            result_text = page.locator("#response").inner_text()
            result = json.loads(result_text)
            assert result["execution_performed"] is False
            assert result["hypergraph_projection_status"] == "available", result
            projection = result["hypergraph_projection"]
            assert projection["schema"] == "taas.hypergraph-projection/v1"
            assert projection["vertices"]
            assert projection["hyperedges"]

            page.locator("#hg-workspace").wait_for(state="visible")
            assert page.locator("#hg-filter").is_enabled()
            assert page.locator("#hg-entity-list button").count() > 0
            assert "Rendered directly from the API projection" in page.locator("#hg-status").inner_text()
            assert "No MCP calls or execution performed" in page.locator("#hg-status").inner_text()

            # Search/filter is presentation-only and does not alter the server response.
            page.locator("#hg-filter").fill("list_orders")
            visible_entities = page.locator("#hg-entity-list button:visible")
            assert visible_entities.count() >= 1
            assert all(
                "list_orders" in visible_entities.nth(i).inner_text().lower()
                for i in range(visible_entities.count())
            )
            page.locator("#hg-filter").fill("")

            # Inspect through the SVG keyboard interaction path.
            edge = page.locator('.hg-entity[role="button"][aria-label="Inspect tool list_orders"]')
            edge.wait_for(state="visible")
            edge.focus()
            edge.press("Enter")
            assert page.locator("#hg-inspector-title").inner_text() == "list_orders"
            inspector_text = page.locator("#hg-inspector-body").inner_text()
            assert "Fired in reachability" in inspector_text
            assert "Fingerprint" in inspector_text

            # The list fallback is also operable by pointer and updates the inspector.
            list_edge = page.locator('#hg-entity-list button').filter(has_text="list_orders").first
            list_edge.click()
            assert page.locator("#hg-inspector-title").inner_text() == "list_orders"

            # Responsive layout: the graph and inspector stack at a narrow viewport.
            page.set_viewport_size({"width": 390, "height": 844})
            grid_columns = page.locator("#hg-workspace").evaluate(
                "(el) => getComputedStyle(el).gridTemplateColumns"
            )
            assert len(grid_columns.split()) == 1, grid_columns
            assert page.locator("#hg-inspector-title").is_visible()

            # Return to desktop for a reproducible visual artifact in Colab.
            page.set_viewport_size({"width": 1440, "height": 1000})
            screenshot = tmp_path / "hypergraph-explorer-browser-e2e.png"
            page.locator("#hypergraph-explorer").screenshot(path=str(screenshot))
            assert screenshot.is_file() and screenshot.stat().st_size > 0
            assert not mcp_requests, f"Unexpected MCP HTTP requests: {mcp_requests}"
            browser.close()

        screenshot_target = os.environ.get("TAAS_E2E_SCREENSHOT")
        if screenshot_target:
            target = Path(screenshot_target)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(screenshot.read_bytes())
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
