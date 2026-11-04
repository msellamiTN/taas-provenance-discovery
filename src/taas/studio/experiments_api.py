"""First-party PaMCP experiment workbench API.

This initial slice exposes the frozen catalog and validates planned run envelopes.
It deliberately does not execute experiments, call MCP tools, or expose evaluator labels.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from taas.experiments.catalog import CATALOG_PATH, VARIANTS, load_catalog
from taas.experiments.baseline_catalog import (baseline_index, baselines_for_experiment, load_baseline_catalog, validate_baseline_selection)

app = FastAPI(
    title="PaMCP Experimental Workbench API",
    version="1.0.0",
    description="Versioned experimental catalog and run-envelope validation. No execution endpoint is enabled yet.",
)
bearer = HTTPBearer(auto_error=False)


def require_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    expected = os.environ.get("TAAS_STUDIO_API_TOKEN", "")
    supplied = credentials.credentials if credentials else ""
    if not expected:
        raise HTTPException(status_code=503, detail="Studio API token is not configured")
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


class RunDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str = Field(pattern=r"^E([1-9]|1[0-9]|2[0-2])$")
    variant: str
    dataset_snapshot: dict[str, Any]
    split: str = Field(min_length=1, max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)
    seeds: list[int] = Field(default_factory=lambda: [0], min_length=1, max_length=100)
    baseline: str | None = None
    resource_budget: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pamcp-experiment-workbench"}


@app.get("/api/v1/experiments/catalog", dependencies=[Depends(require_token)])
def experiment_catalog(
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=120),
) -> dict[str, Any]:
    data = load_catalog()
    items = data["experiments"]
    if status_filter:
        items = [e for e in items if e.get("status") == status_filter]
    if q:
        ql = q.casefold()
        items = [e for e in items if ql in (e["id"] + " " + e["title"] + " " + " ".join(e["datasets"])).casefold()]
    return {
        "schema_version": data["schema_version"],
        "total": len(items),
        "planned_not_run": sum(e["status"] == "planned_not_run" for e in items),
        "experiments": items,
        "results_loaded": False,
        "baseline_catalog_version": load_baseline_catalog()["schema_version"],
    }


@app.get("/api/v1/experiments/catalog/{experiment_id}", dependencies=[Depends(require_token)])
def experiment_detail(experiment_id: str) -> dict[str, Any]:
    data = load_catalog()
    item = next((e for e in data["experiments"] if e["id"] == experiment_id.upper()), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown experiment ID")
    return item


@app.get("/api/v1/baselines/catalog", dependencies=[Depends(require_token)])
def baseline_catalog(
    q: str | None = Query(None, max_length=120),
    kind: str | None = Query(None, max_length=80),
    experiment_id: str | None = Query(None, pattern=r"^E([1-9]|1[0-9]|2[0-2])$"),
) -> dict[str, Any]:
    data = load_baseline_catalog()
    items = data["baselines"]
    if q:
        needle = q.casefold()
        items = [x for x in items if needle in (x["id"] + " " + x["name"] + " " + x["method"]).casefold()]
    if kind:
        items = [x for x in items if x.get("kind") == kind]
    if experiment_id:
        allowed = {x["id"] for x in baselines_for_experiment(experiment_id)}
        items = [x for x in items if x["id"] in allowed]
    return {
        "schema_version": data["schema_version"],
        "total": len(items),
        "baselines": items,
        "fidelity_warning": "Adapter availability is not a claim of exact published-method reproduction.",
    }


@app.get("/api/v1/baselines/catalog/{baseline_id}", dependencies=[Depends(require_token)])
def baseline_detail(baseline_id: str) -> dict[str, Any]:
    item = baseline_index().get(baseline_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown baseline ID")
    return item


@app.get("/api/v1/experiments/catalog/{experiment_id}/baselines", dependencies=[Depends(require_token)])
def experiment_baselines(experiment_id: str) -> dict[str, Any]:
    try:
        items = baselines_for_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "experiment_id": experiment_id.upper(),
        "total": len(items),
        "baselines": items,
        "selection_rule": "Only listed baselines are valid for this experiment.",
    }


@app.get("/api/v1/experiments/variants", dependencies=[Depends(require_token)])
def variants() -> dict[str, Any]:
    data = load_catalog()
    return {
        "variants": data["pa_mcp_variants"],
        "factorial_design": data["factorial_design"],
        "note": "Leave-one-out contrasts are conditional marginal effects; they are not assumed additive.",
    }


@app.post("/api/v1/experiments/validate", dependencies=[Depends(require_token)])
def validate_run_draft(payload: RunDraft) -> dict[str, Any]:
    data = load_catalog()
    exp = next((e for e in data["experiments"] if e["id"] == payload.experiment_id), None)
    if exp is None:
        raise HTTPException(status_code=404, detail="Unknown experiment")
    if payload.variant not in VARIANTS:
        raise HTTPException(status_code=422, detail=f"Unknown PaMCP variant: {payload.variant}")
    if not isinstance(payload.dataset_snapshot.get("name"), str) or not payload.dataset_snapshot["name"]:
        raise HTTPException(status_code=422, detail="dataset_snapshot.name is required")
    if not isinstance(payload.dataset_snapshot.get("version_or_hash"), str) or not payload.dataset_snapshot["version_or_hash"]:
        raise HTTPException(status_code=422, detail="dataset_snapshot.version_or_hash must be frozen before run creation")
    if len(set(payload.seeds)) != len(payload.seeds):
        raise HTTPException(status_code=422, detail="seeds must be unique")
    if payload.baseline is not None:
        try:
            validate_baseline_selection(payload.experiment_id, [payload.baseline])
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    digest_payload = payload.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "valid": True,
        "run_id": str(uuid.uuid4()),
        "status": "validated_not_queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "configuration": digest_payload,
        "configuration_sha256": digest,
        "experiment_title": exp["title"],
        "variant_factors": {k: getattr(VARIANTS[payload.variant], k) for k in ("G", "P", "S")},
        "execution_enabled": False,
        "evaluator_access_granted": False,
        "message": "Configuration validated only. No experiment has been queued or executed.",
    }


@app.get("/api/v1/experiments/workbench/status", dependencies=[Depends(require_token)])
def workbench_status() -> dict[str, Any]:
    data = load_catalog()
    return {
        "catalog_version": data["schema_version"],
        "experiment_count": len(data["experiments"]),
        "planned_not_run": sum(e["status"] == "planned_not_run" for e in data["experiments"]),
        "run_store": "not_implemented",
        "sequential_runner": "not_implemented",
        "independent_evaluator": "not_implemented",
        "mcp_execution_sandbox": "not_implemented",
        "execution_enabled": False,
    }
