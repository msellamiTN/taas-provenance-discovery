"""Structural and syntax checks for the maintained Colab deployment notebook."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "colab" / "taas_core_studio_colab.ipynb"
GUIDE = ROOT / "docs" / "deployment" / "COLAB_T4_QUICKSTART.md"


def test_colab_notebook_is_valid_and_has_operator_guide() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert GUIDE.is_file()
    assert "COLAB_T4_QUICKSTART.md" in "".join(notebook["cells"][0]["source"])


def test_colab_code_cells_are_valid_python() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells, "Notebook must contain executable code cells"
    for index, cell in enumerate(code_cells):
        source = "".join(cell.get("source", []))
        compile(source, f"colab-cell-{index}", "exec")


def test_colab_notebook_uses_pinned_revision_and_safe_bind_address() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )
    assert 'TAAS_COMMIT = "3f74c753a9a93629ecee2718620fb06bd3affc82"' in source
    assert 'APP_HOST, APP_PORT = "127.0.0.1", 8000' in source
    assert "google.colab.kernel.proxyPort" in source
    assert "trycloudflare.com" not in source
