# TaaS Studio — single-container preprod image.
#
# The package is installed editable from the copied source tree because Core
# modules resolve repository data (data/raw, data/processed) relative to the
# source file (Path(__file__).parents[3]). A regular wheel install would break
# registry/theta resolution and omit static/index.html. This is intentional
# for the single-instance preprod target; a proper package-data refactor is
# tracked separately.
#
# No secrets are baked in. TAAS_STUDIO_API_TOKEN (and optionally named API
# keys) must be supplied at runtime. All persistent state goes to /data,
# which should be a mounted volume in real deployments.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TAAS_AUDIT_LEDGER_PATH=/data/audit.sqlite3 \
    TAAS_AGENT_REGISTRY_PATH=/data/agents.sqlite3 \
    TAAS_SKILL_REGISTRY_PATH=/data/skills.sqlite3 \
    TAAS_WORKSPACES_PATH=/data/workspaces.sqlite3 \
    TAAS_DISCOVERY_RUNS_PATH=/data/runs.sqlite3 \
    TAAS_EVIDENCE_DB_PATH=/data/evidence.sqlite3 \
    TAAS_API_KEYS_PATH=/data/api_keys.sqlite3 \
    TAAS_STUDIO_ACTOR=studio-api

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir -e ".[studio]"

RUN useradd --system --uid 10001 --home /data taas \
    && mkdir -p /data \
    && chown -R taas:taas /data /app
USER taas

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)"

# Auth is fail-closed: without TAAS_STUDIO_API_TOKEN (or an active named key)
# every /api/v1 route returns 503/401. /health and /ready stay public.
CMD ["python", "-m", "uvicorn", "taas.studio.api:app", \
     "--host", "0.0.0.0", "--port", "8000"]
