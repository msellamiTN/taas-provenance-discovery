from pathlib import Path


ROOT = Path(__file__).parents[1]
DOCKERFILE = ROOT / "deploy" / "hf-studio" / "Dockerfile"
SPACE_README = ROOT / "deploy" / "hf-studio" / "README.md"


def test_huggingface_staging_deployment_uses_existing_fastapi_studio():
    docker = DOCKERFILE.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in docker
    assert "COPY src ./src" in docker
    assert "COPY data ./data" in docker
    assert "PYTHONPATH=/app/src" in docker
    assert "taas.studio.api:app" in docker
    assert '"7860"' in docker


def test_staging_space_documents_required_api_secret_and_isolation():
    readme = SPACE_README.read_text(encoding="utf-8")
    assert "sdk: docker" in readme
    assert "app_port: 7860" in readme
    assert "TAAS_STUDIO_API_TOKEN" in readme
    assert "separate private staging Space" in readme
    assert "does not replace MSellami/TAAS_Studio" in readme
