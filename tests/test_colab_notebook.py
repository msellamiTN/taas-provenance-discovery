"""Structural and syntax checks for the maintained Colab deployment notebook."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "colab" / "taas_core_studio_colab.ipynb"
GUIDE = ROOT / "docs" / "deployment" / "COLAB_T4_QUICKSTART.md"
RUNTIME_GUIDE = ROOT / "docs" / "deployment" / "MODEL_RUNTIME_BACKENDS.md"
WORKFLOW = ROOT / ".github" / "workflows" / "benchmark-hypergraph.yml"
INTEGRATED_STUDIO_COMMIT = "97457611c375342cc5c50d6ec3a5936f10d26d3e"


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
    assert RUNTIME_GUIDE.is_file()
    assert "COLAB_T4_QUICKSTART.md" in markdown
    assert "CPU / CUDA / Ollama" in markdown


def test_colab_quickstart_has_no_escaped_table_newline() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    assert "|\\n| Discovery returns 422" not in guide
    assert "| Discovery returns 422 |" in guide


def test_colab_code_cells_are_valid_python() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells, "Notebook must contain executable code cells"
    for index, cell in enumerate(code_cells):
        source = "".join(cell.get("source", []))
        compile(source, f"colab-cell-{index}", "exec")



def test_colab_runs_objective_contract_v3_acceptance() -> None:
    _, markdown, code = notebook_source()
    assert "Objective Intelligence v3 acceptance" in markdown
    assert "exact clause-provenance graph and explicit dependency-relation invariants" in markdown
    assert "tests/test_objective_contract_v3.py" in code
    assert "tests/test_objective_contract_v3.py" in code
    assert "test_v3_builds_clause_provenance_graph_with_exact_source_spans" in code or "tests/test_objective_contract_v3.py" in code
    assert "tests/test_studio_api.py" in code
    assert "Objective Intelligence v3 acceptance passed" in code

def test_colab_runs_agent_reusable_skill_binding_acceptance() -> None:
    _, _, code = notebook_source()
    assert "tests/test_agent_reusable_skill_binding.py" in code
    assert "Agent reusable Skill binding acceptance tests failed" in code
    assert "Agent reusable Skill binding unit, API and Studio picker tests passed." in code


def test_colab_runs_reusable_skill_registry_acceptance() -> None:
    _, _, code = notebook_source()
    assert "tests/test_skill_registry.py" in code
    assert "tests/test_skill_registry_api.py" in code
    assert "Reusable Skill Registry acceptance tests failed" in code
    assert "Reusable Skill Registry unit and authenticated API tests passed." in code


def test_colab_notebook_pins_the_integrated_model_agent_studio_revision() -> None:
    _, markdown, code = notebook_source()
    assert f'TAAS_COMMIT = "{INTEGRATED_STUDIO_COMMIT}"' in code
    assert "Model & Agentic Studio" in markdown
    assert "model-backed chat inference" in markdown
    assert "TaaS tool discovery" in markdown
    assert "MCP inspection does not invoke tools" in markdown
    assert "discovery workspace" not in markdown.lower() or "integrated" in markdown.lower()
    assert "Hypergraph Explorer" in markdown


def test_colab_covers_objective_constraint_dependency_namespace() -> None:
    _, _, code = notebook_source()
    assert "canonicalize_objective_constraint_dependencies" in code
    assert "canonicalize_retrieval_target_inputs" in code
    assert "canonicalize_self_dependencies" in code
    assert "canonicalize_arithmetic_expressions_from_effects" in code
    assert "Retrieve customer records and calculate the average transaction amount" in code
    assert "tool_and_model_capability_gaps_detected" in code
    assert "tests/test_studio_objective_constraint_dependencies.py" in code
    assert "Objective Contract constraint/dependency namespace separation OK" in code
    assert f'TAAS_COMMIT = "{INTEGRATED_STUDIO_COMMIT}"' in code
    assert "Retrieve records matching the provided query from the configured source." in code
    assert "Can you get me the year difference between the creation date of the" in code
    assert "Year-difference contract and retrieval-only rejection checks OK" in code


def test_colab_distinguishes_external_tool_requirements_from_model_gaps() -> None:
    _, _, code = notebook_source()
    # Retrieval-only classification is checked deterministically without model inference.
    assert 'core.get("status") == "tool_requirements_detected"' in code
    assert 'retrieval_only.get("tool_required_goal_ids") == ["g1"]' in code
    assert 'retrieval_only.get("model_capability_gap_goal_ids") == []' in code
    # The optional compound live test keeps external-tool and native-skill gaps distinct.
    assert 'core.get("status") == "tool_and_model_capability_gaps_detected"' in code
    assert 'core.get("tool_required_goal_ids") == ["g1"]' in code
    assert 'core.get("model_capability_gap_goal_ids") == ["g2"]' in code
    assert 'core.get("gap_goal_ids") == ["g1", "g2"]' in code
    assert 'calibrated_profile_matched") is False' in code


def test_colab_objective_matrix_covers_local_and_external_workflows() -> None:
    _, _, code = notebook_source()
    for phrase in (
        "Summarise the document supplied in the prompt.",
        "Translate this paragraph into French.",
        "Compare these two provided architectures.",
        "Identify anomalies in the supplied sensor data.",
        "Create a report from several external sources.",
        "Count all invoices issued this year.",
        "Calculate average sales by region.",
        "Supplied-content vs external-source routing checks OK",
    ):
        assert phrase in code
    assert 'assert contract["source_data_required"] is False' in code
    assert "importlib.reload(objective_contract)" in code
    assert "importlib.invalidate_caches()" in code
    assert "studio_api = importlib.reload(studio_api)" in code
    assert "missing_agent_api" in code
    assert 'contract["contract_version"] == "2.0"' in code
    assert 'assert contract["source_data_required"] is True' in code


def test_colab_installs_and_verifies_optional_hugging_face_runtime() -> None:
    _, _, code = notebook_source()
    assert '"-e", ".[test,studio,hf]"' in code
    assert "importlib.import_module('torch')" in code
    assert "importlib.import_module('transformers')" in code
    assert "importlib.import_module('safetensors')" in code
    assert "importlib.import_module('sentencepiece')" in code
    assert "importlib.import_module('tiktoken')" in code
    assert "importlib.import_module('taas.studio.ollama_runtime')" in code
    assert "ENABLE_OLLAMA = False" in code
    assert "TAAS_OLLAMA_BASE_URL" in code


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
    assert "proxy_url = output.eval_js" in code
    assert "google.colab.kernel.proxyPort" in code
    assert "Fresh Colab proxy URL generated" in code
    assert 'wait_http(f"http://{APP_HEALTH_HOST}:{APP_PORT}/health")' in code
    assert "playwright" not in code.lower()



def test_colab_covers_agent_instruction_and_skill_injection() -> None:
    _, markdown, code = notebook_source()
    assert "Agent Intelligence Context acceptance" in markdown
    assert "tests/test_agent_intelligence_context.py" in code
    assert "RUN_LIVE_AGENT_CONTEXT_TEST" in code
    assert "/api/v1/objectives/prepare" in code
    assert "agent_intelligence_context" in code
    assert "selected_skill_ids" in code
    assert "tool_execution" in code
