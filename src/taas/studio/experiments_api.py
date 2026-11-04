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

from taas.contracts import extract_contract
from taas.effects import parse_effect
from taas.model_profile import EXTERNAL_CLASSES, MODEL_CLASSES
from taas.data.registries import RawTool
from taas.experiments.baseline_runner import run_baseline
from taas.experiments.registry_baselines import run_effect_baseline, run_typing_baseline
from taas.experiments.policy_baselines import run_policy_baseline
from taas.goals import parse_goal_spec
from taas.policy import Policy
from taas.retrieval import HybridRetriever
from taas.types import KINDS

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



class BaselineToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None
    source: str = "baseline-preview"
    category: str = ""


class BaselinePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str = Field(pattern=r"^E([1-9]|1[0-9]|2[0-2])$")
    baseline_ids: list[str] = Field(min_length=1, max_length=32)
    goal_spec: dict[str, Any]
    tools: list[BaselineToolInput] = Field(min_length=1, max_length=2000)
    policy: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(default=5, ge=1, le=100)
    parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    training_scenes: list[dict[str, Any]] | None = Field(default=None, max_length=20000)
    trajectories: list[dict[str, Any]] | None = Field(default=None, max_length=20000)



def validate_preview_goal_spec(spec: dict[str, Any]) -> None:
    """Strict structural validation before a baseline adapter sees the task."""
    goals = spec.get("goals")
    if not isinstance(goals, list) or not goals:
        raise HTTPException(status_code=422, detail="goal_spec.goals must be a non-empty array")
    allowed_classes = set(MODEL_CLASSES) | set(EXTERNAL_CLASSES)
    legacy_fields = {"output", "reason", "dependencies"}
    type_pattern = re.compile(r"^([a-z_]+)(?::[a-z0-9_-]+)?(\\[\\])?$")

    def valid_type(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        match = type_pattern.fullmatch(value)
        return bool(match and match.group(1) in KINDS)

    ids: list[str] = []
    for index, goal in enumerate(goals):
        prefix = f"goal_spec.goals[{index}]"
        if not isinstance(goal, dict):
            raise HTTPException(status_code=422, detail=f"{prefix} must be an object")
        legacy = sorted(legacy_fields.intersection(goal))
        if legacy:
            raise HTTPException(status_code=422, detail=f"{prefix} uses legacy field(s) {legacy}")
        goal_id = goal.get("id")
        if not isinstance(goal_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", goal_id):
            raise HTTPException(status_code=422, detail=f"{prefix}.id is invalid")
        if goal_id in ids:
            raise HTTPException(status_code=422, detail=f"duplicate goal id: {goal_id}")
        ids.append(goal_id)
        if goal.get("class") not in allowed_classes:
            raise HTTPException(status_code=422, detail=f"{prefix}.class is unsupported")
        if not valid_type(goal.get("out")):
            raise HTTPException(status_code=422, detail=f"{prefix}.out is not a supported semantic type")
        if goal.get("sigma", "native") not in {"native", "data", "effect", "unreliable"}:
            raise HTTPException(status_code=422, detail=f"{prefix}.sigma is invalid")
        if not isinstance(goal.get("desc"), str) or not goal["desc"].strip():
            raise HTTPException(status_code=422, detail=f"{prefix}.desc must be non-empty")
        for field_name in ("in", "eff", "deps"):
            value = goal.get(field_name, [])
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise HTTPException(status_code=422, detail=f"{prefix}.{field_name} must be a string array")
        for type_value in goal.get("in", []):
            if not valid_type(type_value):
                raise HTTPException(status_code=422, detail=f"{prefix}.in contains an unsupported semantic type")
        for effect_value in goal.get("eff", []):
            try:
                parse_effect(effect_value)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"{prefix}.eff contains an invalid effect") from exc
        if "optional" in goal and not isinstance(goal["optional"], bool):
            raise HTTPException(status_code=422, detail=f"{prefix}.optional must be boolean")
        if "n" in goal and (isinstance(goal["n"], bool) or not isinstance(goal["n"], int) or goal["n"] < 1):
            raise HTTPException(status_code=422, detail=f"{prefix}.n must be a positive integer")
        if goal.get("exactness", "tolerant") not in {"tolerant", "exact"}:
            raise HTTPException(status_code=422, detail=f"{prefix}.exactness is invalid")
    prompt_inputs = spec.get("prompt_inputs", ["text"])
    if not isinstance(prompt_inputs, list) or any(not valid_type(x) for x in prompt_inputs):
        raise HTTPException(status_code=422, detail="goal_spec.prompt_inputs must contain supported semantic types")
    for index, goal in enumerate(goals):
        for dependency in goal.get("deps", []):
            if dependency not in ids or dependency == ids[index]:
                raise HTTPException(status_code=422, detail=f"goal {ids[index]} has an invalid dependency {dependency!r}")
    parsed = parse_goal_spec(spec, prompt=str(spec.get("prompt", "")))
    if parsed.order() is None:
        raise HTTPException(status_code=422, detail="goal_spec dependency graph contains a cycle")


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



@app.post("/api/v1/baselines/preview", dependencies=[Depends(require_token)])
def baseline_preview(payload: BaselinePreviewRequest) -> dict[str, Any]:
    """Execute selected baseline adapters over a supplied registry snapshot; never scores gold labels."""
    try:
        selected = validate_baseline_selection(payload.experiment_id, payload.baseline_ids)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    validate_preview_goal_spec(payload.goal_spec)
    spec = parse_goal_spec(payload.goal_spec, prompt=str(payload.goal_spec.get("prompt", "")))

    raw_tools = [RawTool(**tool.model_dump()) for tool in payload.tools]
    contracts = [extract_contract(tool) for tool in raw_tools]
    if len({c.tool for c in contracts}) != len(contracts):
        raise HTTPException(status_code=422, detail="Tool identities must be unique (server::name)")
    retriever = HybridRetriever().fit(contracts)
    pool = list(retriever.contracts)
    policy_data = payload.policy
    try:
        policy = Policy.make(
            name=str(policy_data.get("name", "baseline-preview")),
            required=policy_data.get("required", []),
            allowed=policy_data.get("allowed", ["read(*)", "egress(*)", "session"]),
            lmin=policy_data.get("lmin", "obs"),
            forbidden=policy_data.get("forbidden", []),
            encoding=policy_data.get("encoding", "positive"),
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid baseline policy: {exc}") from exc

    canonical_tools = sorted(
        [tool.model_dump(mode="json") for tool in payload.tools],
        key=lambda item: (item["server"], item["name"]),
    )
    registry_hash = hashlib.sha256(json.dumps(canonical_tools, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    policy_payload = dict(policy_data)
    policy_hash = hashlib.sha256(json.dumps(policy_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    tool_hashes = {contract.tool: contract.h for contract in contracts}
    prompt = str(payload.goal_spec.get("prompt", ""))
    results = []
    for baseline in selected:
        baseline_id = baseline["id"]
        params = payload.parameters.get(baseline_id, {})
        try:
            if baseline_id in {"typing_structural", "typing_schema_lexical"}:
                result = run_typing_baseline(baseline_id, raw_tools)
            elif baseline_id in {"effects_declared", "effects_lexical", "effects_probe"}:
                result = run_effect_baseline(baseline_id, raw_tools)
            elif baseline_id in {"mcp_default_annotations", "closed_world_annotations", "lexical_positive", "lexical_closed_world", "verified_evidence"}:
                result = run_policy_baseline(baseline_id, raw_tools)
            else:
                result = run_baseline(
                    baseline_id, retriever, spec, prompt, pool, top_k=payload.top_k,
                    policy=policy, training_scenes=payload.training_scenes,
                    trajectories=payload.trajectories, registry_hash=registry_hash,
                    policy_hash=policy_hash, tool_hashes=tool_hashes, parameters=params,
                ).to_dict()
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            result = {
                "baseline_id": baseline_id,
                "status": "invalid_adapter_configuration",
                "selected_tools": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append({"baseline": baseline, "result": result})

    return {
        "experiment_id": payload.experiment_id,
        "baseline_count": len(results),
        "registry_snapshot": {"tool_count": len(pool), "sha256": registry_hash},
        "goal_spec": payload.goal_spec,
        "results": results,
        "evaluator_labels_accessed": False,
        "mcp_tools_executed": False,
        "execution_kind": "baseline_adapter_preview",
        "note": "This is a baseline-adapter preview, not a persisted E1-E22 run. Gold-label evaluation is not performed.",
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
