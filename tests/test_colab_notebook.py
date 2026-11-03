"""Structural and syntax checks for the maintained Colab deployment notebook."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "colab" / "taas_core_studio_colab.ipynb"
GUIDE = ROOT / "docs" / "deployment" / "COLAB_T4_QUICKSTART.md"
WORKFLOW = ROOT / ".github" / "workflows" / "benchmark-hypergraph.yml"
INTEGRATED_STUDIO_COMMIT = "888fefa5f14ad31ef367a7bdf560fcd1c6f0338e"


def notebook_source() -> tuple[dict, str, str]:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    markdown = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "markdown"
    )
    code = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )
    return notebook, markdown, code


def test_colab_notebook_is_valid_and_has_operator_guide() -> None:
    notebook, markdown, _ = notebook_source()
    assert notebook["nbformat"] == 4
    assert GUIDE.is_file()
    assert "COLAB_T4_QUICKSTART.md" in markdown


def test_colab_code_cells_are_valid_python() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells, "Notebook must contain executable code cells"
    for index, cell in enumerate(code_cells):
        source = "".join(cell.get("source", []))
        compile(source, f"colab-cell-{index}", "exec")


def test_colab_notebook_pins_the_integrated_model_agent_studio_revision() -> None:
    _, markdown, code = notebook_source()
    assert f'TAAS_COMMIT = "{INTEGRATED_STUDIO_COMMIT}"' in code
    assert "Model & Agentic Studio" in markdown
    assert "model-backed chat inference" in markdown
    assert "TaaS tool discovery" in markdown
    assert "MCP inspection does not invoke tools" in markdown
    assert "discovery workspace" not in markdown.lower() or "integrated" in markdown.lower()
    assert "Hypergraph Explorer" in markdown


def test_colab_installs_and_verifies_optional_hugging_face_runtime() -> None:
    _, _, code = notebook_source()
    assert '"-e", ".[studio,hf]"' in code
    assert "importlib.import_module('torch')" in code
    assert "importlib.import_module('transformers')" in code
    assert "importlib.import_module('safetensors')" in code


def test_colab_notebook_uses_safe_loopback_proxy_and_ephemeral_token() -> None:
    _, _, code = notebook_source()
    assert 'APP_BIND_HOST, APP_HEALTH_HOST, APP_PORT = "0.0.0.0", "127.0.0.1", 8000' in code
    assert "google.colab.kernel.proxyPort" in code
    assert "trycloudflare.com" not in code
    assert "secrets.token_urlsafe(32)" in code
    assert 'os.environ.pop("TAAS_MODEL_PROFILE"' in code
    assert "files.upload" not in code


def test_ci_covers_stacked_studio_pull_requests() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    # A stacked PR may target any feature branch, not only historical bases.
    pull_request_block = workflow.split("  pull_request:", 1)[1].split("  workflow_dispatch:", 1)[0]
    assert "branches:" not in pull_request_block


MCP_REGISTRY_NOTEBOOK = ROOT / "notebooks" / "colab" / "taas_agent_mcp_registry_pr27_colab.ipynb"
MCP_INTEGRATED_VALIDATED_COMMIT = "729a1b6922deba7f2c57a96a899514b787e3c7e6"


def test_mcp_colab_notebook_pins_the_integrated_agent_mcp_revision() -> None:
    notebook = json.loads(MCP_REGISTRY_NOTEBOOK.read_text(encoding="utf-8"))
    markdown = "\\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "markdown"
    )
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    code = "\\n".join("".join(cell.get("source", [])) for cell in code_cells)

    assert notebook["nbformat"] == 4
    assert code_cells
    for index, cell in enumerate(code_cells):
        compile("".join(cell.get("source", [])), f"mcp-colab-cell-{index}", "exec")

    assert f'TAAS_COMMIT = "{MCP_INTEGRATED_VALIDATED_COMMIT}"' in code
    assert "pull/34" in markdown
    assert "/api/v1/agents" in code
    assert "/api/v1/mcp/registry/snapshots" in code
    assert "google.colab.kernel.proxyPort" in code
    assert "tool_execution_performed" not in code


def test_colab_reuses_the_single_studio_runtime_and_proxy_without_browser_automation() -> None:
    _, markdown, code = notebook_source()
    assert "one checkout" in markdown
    assert "one Studio process" in markdown
    assert 'if "proxy_url" not in globals() or not proxy_url:' in code
    assert "google.colab.kernel.proxyPort" in code
    assert "playwright" not in code.lower()
