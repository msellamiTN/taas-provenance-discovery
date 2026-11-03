"""Structural and syntax checks for the maintained Colab deployment notebook."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "colab" / "taas_core_studio_colab.ipynb"
GUIDE = ROOT / "docs" / "deployment" / "COLAB_T4_QUICKSTART.md"
WORKFLOW = ROOT / ".github" / "workflows" / "benchmark-hypergraph.yml"
INTEGRATED_STUDIO_COMMIT = "1dd15b069fc847d0262bc416980bb6a7ede7b731"


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


def test_colab_installs_and_verifies_optional_hugging_face_runtime() -> None:
    _, _, code = notebook_source()
    assert '"-e", ".[studio,hf]"' in code
    assert "importlib.import_module('torch')" in code
    assert "importlib.import_module('transformers')" in code
    assert "importlib.import_module('safetensors')" in code


def test_colab_notebook_uses_safe_loopback_proxy_and_ephemeral_token() -> None:
    _, _, code = notebook_source()
    assert 'APP_HOST, APP_PORT = "127.0.0.1", 8000' in code
    assert "google.colab.kernel.proxyPort" in code
    assert "trycloudflare.com" not in code
    assert "secrets.token_urlsafe(32)" in code
    assert 'os.environ.pop("TAAS_MODEL_PROFILE"' in code
    assert "files.upload" not in code


def test_ci_covers_stacked_studio_pull_requests() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "feature/colab-model-agent-studio" in workflow
    # A stacked PR may target another feature branch, not only main.
    pull_request_block = workflow.split("  pull_request:", 1)[1].split("  workflow_dispatch:", 1)[0]
    assert "branches:" not in pull_request_block
