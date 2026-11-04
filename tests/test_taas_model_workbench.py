from pathlib import Path

PAGE = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


def test_model_catalog_renders_selectable_repository_cards():
    html = PAGE.read_text(encoding="utf-8")
    for marker in (
        'id="model-cards"',
        'id="model-selected-panel"',
        'id="model-selected-details"',
        'id="model-use-runtime"',
        'id="model-inspect-artifacts"',
        'id="model-selected-artifacts"',
    ):
        assert marker in html
    assert "createElement(\"article\")" in html
    assert "action.addEventListener(\"click\",()=>selectModel(model.model_id))" in html
    assert "textContent=model.model_id" in html


def test_model_workbench_uses_live_detail_artifact_and_memory_endpoints():
    html = PAGE.read_text(encoding="utf-8")
    assert "/api/v1/models/detail?" in html
    assert "/api/v1/models/artifacts?" in html
    assert "/api/v1/models/estimate-memory" in html
    assert "/api/v1/models/load" in html
    assert "load_guaranteed" not in html  # the UI must not fabricate a load guarantee
    assert "not a guarantee of successful loading" in html.lower()


def test_kv_cache_estimate_is_sent_only_with_complete_architecture_dimensions():
    html = PAGE.read_text(encoding="utf-8")
    assert 'const kvKeys=["num_hidden_layers","num_key_value_heads","head_dim"]' in html
    assert "const kvComplete=kvKeys.every" in html
    assert "if(kvComplete)" in html
    assert "KV cache excluded because complete architecture dimensions were unavailable." in html


def test_catalog_selection_does_not_claim_runtime_compatibility_or_execute_code():
    html = PAGE.read_text(encoding="utf-8")
    assert "weights downloaded: no" in html
    assert "runtime compatibility unverified" in html
    assert "model_code_executed" in html or "remote repository code execution is disabled" in html
    assert "trust_remote_code=false" in html

def test_overview_exposes_taas_lifecycle_and_marks_execution_gateway_truthfully():
    html = PAGE.read_text(encoding="utf-8")
    for marker in (
        "TaaS engineering lifecycle",
        "Agent planning",
        "Tool intelligence",
        "Goal contract",
        "Discovery",
        "Assurance",
        "Execution gateway",
        "Authorization primitives only · no invocation API",
    ):
        assert marker in html
    assert 'document.querySelectorAll(".pipeline-step[href]")' in html
    assert 'const destination = studioLinks.find(link => link.getAttribute("href") === step.getAttribute("href"));' in html
    assert "if (destination)" in html
    assert "showStudioWorkspace(destination);" in html
