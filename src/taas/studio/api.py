"""Minimal HTTP boundary for the existing TaaS discovery core.

This is an experimental API, not a production-hardened multi-tenant service.
Protect it behind an authenticated tunnel/reverse proxy and keep it bound to loopback.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from taas.contracts import extract_contract
from taas.effects import parse_effect
from taas.data.registries import RawTool, load_processed
from taas.engine import DiscoveryEngine, EngineConfig
from taas.model_profile import EXTERNAL_CLASSES, MODEL_CLASSES, ModelProfile
from taas.goals import SIGMAS, parse_goal_spec
from taas.policy import Policy
from taas.provenance import DEFAULT_TRUST
from taas.studio.models import ModelCatalogError, get_model_details, inspect_model_artifacts, search_models
from taas.studio.agent_spec import validate_agent_manifest
from taas.studio import agent_registry
from taas.studio.authorization_preflight import (
    AuthorizationConfigurationError,
    build_authorization_preflight,
    load_trusted_authorization_config,
)
from taas.studio.runtime import estimate_model_memory, probe_hardware, probe_runtime
from taas.studio.model_runtime import ModelRuntimeError, get_model_runtime
from taas.studio.mcp_registry import MCPRegistryError, inspect_server as inspect_mcp_server, list_servers as list_mcp_servers
from taas.types import KINDS
from taas.studio.assurance_routes import build_assurance_router

app = FastAPI(
    title="TaaS Core Studio API",
    version="0.1.0",
    description="Experimental API wrapper around the existing TaaS discovery engine.",
)
bearer = HTTPBearer(auto_error=False)


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None
    source: str = "studio-user"
    category: str = ""


class ModelMemoryEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameters_billion: float = Field(gt=0, le=200)
    quantization: str = Field(default="int4", pattern="^(fp16|int8|int4)$")
    overhead_fraction: float = Field(default=0.20, ge=0, le=1)
    runtime_reserve_gib: float = Field(default=2.0, ge=0, le=64)
    num_hidden_layers: int | None = Field(default=None, gt=0, le=512)
    num_key_value_heads: int | None = Field(default=None, gt=0, le=512)
    head_dim: int | None = Field(default=None, gt=0, le=16384)
    context_length: int | None = Field(default=None, gt=0, le=1000000)
    batch_size: int = Field(default=1, ge=1, le=128)
    kv_cache_dtype: str = Field(default="fp16", pattern="^(fp16|int8|fp32)$")


class DiscoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_spec: dict[str, Any]
    tools: list[ToolInput] = Field(min_length=1, max_length=500)
    policy: dict[str, Any] = Field(default_factory=dict)
    engine: dict[str, Any] = Field(default_factory=dict)


class ModelLoadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(min_length=3, max_length=257)
    device: str = Field(default="auto", pattern="^(auto|cpu|cuda)$")


class ModelChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=12000)
    system: str = Field(default="You are a helpful assistant.", max_length=4000)
    max_new_tokens: int = Field(default=512, ge=1, le=2048)
    temperature: float = Field(default=0.2, ge=0, le=2)


class AgentDecomposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=12000)
    context: str = Field(default="", max_length=8000)
    max_new_tokens: int = Field(default=1200, ge=1, le=2048)


class AgentPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registry_snapshot_id: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )


class AgentAuthorizationPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    tool_name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
    arguments: dict[str, Any]
    goal_spec: dict[str, Any]


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> None:
    expected = os.environ.get("TAAS_STUDIO_API_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Studio API token is not configured",
        )
    supplied = credentials.credentials if credentials else ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


app.include_router(build_assurance_router(require_api_token))


def load_profile() -> ModelProfile:
    """Load optional calibration; otherwise use an explicitly uncalibrated, fail-closed profile.

    This default permits Studio startup and discovery without pretending that model
    capability measurements exist. Unknown native capabilities remain rho=0.
    """
    configured = os.environ.get("TAAS_MODEL_PROFILE", "").strip()
    if not configured:
        return ModelProfile(model_id="uncalibrated-default", strict=True)
    path = Path(configured).expanduser().resolve()
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Configured model profile file does not exist")
    try:
        return ModelProfile.load(path)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load model profile: {type(exc).__name__}") from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "taas-core-studio-api"}


@app.get("/ready")
def ready() -> dict[str, str]:
    if not os.environ.get("TAAS_STUDIO_API_TOKEN"):
        raise HTTPException(status_code=503, detail="API token is not configured")
    # Calibration is optional at startup. Discovery uses a strict, uncalibrated
    # profile until an operator configures a measured profile in Studio.
    return {"status": "ready", "calibration": "configured" if os.environ.get("TAAS_MODEL_PROFILE") else "uncalibrated"}


@app.get("/api/v1/runtime/hardware", dependencies=[Depends(require_api_token)])
def runtime_hardware() -> dict[str, Any]:
    """Report host GPU and CUDA readiness; does not load or execute a model."""
    return probe_hardware()


@app.get("/api/v1/runtime/status", dependencies=[Depends(require_api_token)])
def runtime_status() -> dict[str, Any]:
    """Report process, host, storage and GPU state; does not load or execute a model."""
    return probe_runtime()


def validate_studio_goal_spec(spec: dict[str, Any]) -> None:
    """Fail early on the legacy/malformed UI payload instead of silently defaulting fields."""
    goals = spec.get("goals")
    if not isinstance(goals, list) or not goals:
        raise HTTPException(status_code=422, detail="goal_spec.goals must be a non-empty array")
    allowed_classes = set(MODEL_CLASSES) | set(EXTERNAL_CLASSES)
    legacy = {"output", "reason", "dependencies"}
    ids: list[str] = []
    type_pattern = re.compile(r"^([a-z_]+)(?::[a-z0-9_-]+)?(\[\])?$")
    def valid_semantic_type(value: str) -> bool:
        match = type_pattern.fullmatch(value)
        return bool(match and match.group(1) in KINDS)

    for index, goal in enumerate(goals):
        prefix = f"goal_spec.goals[{index}]"
        if not isinstance(goal, dict):
            raise HTTPException(status_code=422, detail=f"{prefix} must be an object")
        old = sorted(legacy.intersection(goal))
        if old:
            raise HTTPException(
                status_code=422,
                detail=f"{prefix} uses legacy field(s) {old}; use out, desc and deps",
            )
        goal_id = goal.get("id")
        if not isinstance(goal_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", goal_id):
            raise HTTPException(status_code=422, detail=f"{prefix}.id must be a valid non-empty goal identifier")
        if goal_id in ids:
            raise HTTPException(status_code=422, detail=f"duplicate goal id: {goal_id}")
        ids.append(goal_id)
        cls = goal.get("class")
        if not isinstance(cls, str) or cls not in allowed_classes:
            raise HTTPException(
                status_code=422,
                detail=f"{prefix}.class must be one of the supported model or external goal classes; got {cls!r}",
            )
        out_type = goal.get("out")
        if not isinstance(out_type, str) or not valid_semantic_type(out_type):
            raise HTTPException(status_code=422, detail=f"{prefix}.out must be a semantic type string")
        if goal.get("sigma", "native") not in SIGMAS:
            raise HTTPException(status_code=422, detail=f"{prefix}.sigma must be one of {SIGMAS}")
        for field_name in ("in", "eff", "deps"):
            if field_name in goal and not isinstance(goal[field_name], list):
                raise HTTPException(status_code=422, detail=f"{prefix}.{field_name} must be an array")
        for field_name in ("in", "eff", "deps"):
            if any(not isinstance(item, str) for item in goal.get(field_name, [])):
                raise HTTPException(status_code=422, detail=f"{prefix}.{field_name} must contain strings")
        for input_type in goal.get("in", []):
            if not valid_semantic_type(input_type):
                raise HTTPException(status_code=422, detail=f"{prefix}.in contains invalid semantic type {input_type!r}")
        for effect in goal.get("eff", []):
            try:
                parse_effect(effect)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"{prefix}.eff contains invalid effect {effect!r}") from exc
        n = goal.get("n", 1)
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise HTTPException(status_code=422, detail=f"{prefix}.n must be a positive integer")
        if goal.get("exactness", "tolerant") not in ("tolerant", "exact"):
            raise HTTPException(status_code=422, detail=f"{prefix}.exactness must be tolerant or exact")
        if "optional" in goal and not isinstance(goal["optional"], bool):
            raise HTTPException(status_code=422, detail=f"{prefix}.optional must be a boolean")
        if "lang" in goal and (not isinstance(goal["lang"], str) or not goal["lang"].strip()):
            raise HTTPException(status_code=422, detail=f"{prefix}.lang must be a non-empty string")
        if not isinstance(goal.get("desc"), str) or not goal["desc"].strip():
            raise HTTPException(status_code=422, detail=f"{prefix}.desc must be a non-empty authored goal description")
    prompt_inputs = spec.get("prompt_inputs", ["text"])
    if not isinstance(prompt_inputs, list) or any(not isinstance(item, str) for item in prompt_inputs):
        raise HTTPException(status_code=422, detail="goal_spec.prompt_inputs must be an array of semantic type strings")
    for item in prompt_inputs:
        if not valid_semantic_type(item):
            raise HTTPException(status_code=422, detail=f"goal_spec.prompt_inputs contains invalid semantic type {item!r}")
    if "prompt" in spec and not isinstance(spec["prompt"], str):
        raise HTTPException(status_code=422, detail="goal_spec.prompt must be a string")
    known_ids = set(ids)
    for index, goal in enumerate(goals):
        for dep in goal.get("deps", []):
            if dep not in known_ids:
                raise HTTPException(status_code=422, detail=f"goal {ids[index]} references unknown dependency {dep!r}")
            if dep == ids[index]:
                raise HTTPException(status_code=422, detail=f"goal {ids[index]} cannot depend on itself")
    parsed = parse_goal_spec(spec, prompt=str(spec.get("prompt", "")))
    if parsed.order() is None:
        raise HTTPException(status_code=422, detail="goal_spec dependency graph contains a cycle")


def parse_studio_goal_spec(spec: dict[str, Any]):
    """Parse the core GoalSpec while preserving the Studio natural-language prompt."""
    return parse_goal_spec(spec, prompt=str(spec.get("prompt", "")))



@app.post("/api/v1/goals/validate", dependencies=[Depends(require_api_token)])
def validate_goal_spec_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the canonical GoalSpec contract and dependency DAG; performs no discovery."""
    validate_studio_goal_spec(payload)
    parsed = parse_studio_goal_spec(payload)
    order = parsed.order() or []
    return {
        "valid": True,
        "goal_count": len(parsed.goals),
        "goal_order": [goal.id for goal in order],
        "prompt_inputs": [str(item) for item in parsed.prompt_inputs],
        "semantic_correctness_verified": False,
    }


@app.get("/api/v1/models/search", dependencies=[Depends(require_api_token)])
def model_search(
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(10, ge=1, le=30),
    sort: str = Query("downloads"),
    pipeline_tag: str | None = Query(None, max_length=80),
) -> dict[str, Any]:
    """Search public Hugging Face model metadata; never downloads or loads weights."""
    if not 1 <= limit <= 30:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 30")
    try:
        models = search_models(q, limit=limit, sort=sort, pipeline_tag=pipeline_tag)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"query": q, "count": len(models), "models": models, "weights_downloaded": False}


@app.get("/api/v1/models/detail", dependencies=[Depends(require_api_token)])
def model_detail(
    model_id: str = Query(..., min_length=3, max_length=256),
) -> dict[str, Any]:
    """Return safe HF model/config metadata; does not download or execute artifacts."""
    try:
        return get_model_details(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/models/artifacts", dependencies=[Depends(require_api_token)])
def model_artifacts(
    model_id: str = Query(..., min_length=3, max_length=256),
) -> dict[str, Any]:
    """Inspect repository artifact metadata only; never downloads model files."""
    try:
        return inspect_model_artifacts(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/v1/models/estimate-memory", dependencies=[Depends(require_api_token)])
def model_memory_estimate(request: ModelMemoryEstimateRequest) -> dict[str, Any]:
    """Return a conservative weight-memory estimate; never downloads or loads a model."""
    try:
        return estimate_model_memory(
            parameters_billion=request.parameters_billion,
            quantization=request.quantization,
            overhead_fraction=request.overhead_fraction,
            runtime_reserve_gib=request.runtime_reserve_gib,
            num_hidden_layers=request.num_hidden_layers,
            num_key_value_heads=request.num_key_value_heads,
            head_dim=request.head_dim,
            context_length=request.context_length,
            batch_size=request.batch_size,
            kv_cache_dtype=request.kv_cache_dtype,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



@lru_cache(maxsize=1)
def _bench_data() -> dict[str, Any]:
    """Load the repository-retained benchmark snapshot once per Studio process."""
    return load_processed()


_BENCH_TASK_KEYS = {
    "livemcpbench": "tasks_livemcpbench",
    "mcptoolbenchpp": "tasks_mcptoolbenchpp",
}


@app.get("/api/v1/bench/datasets", dependencies=[Depends(require_api_token)])
def bench_datasets() -> dict[str, Any]:
    """List locally retained benchmark datasets and aggregate registry statistics."""
    data = _bench_data()
    stats = data.get("stats", {})
    datasets = []
    for dataset_id, task_key in _BENCH_TASK_KEYS.items():
        tasks = data.get(task_key, [])
        categories = sorted({str(item.get("category", "")) for item in tasks if item.get("category")})
        datasets.append({
            "id": dataset_id,
            "task_count": len(tasks),
            "categories": categories,
            "source": "repository-retained snapshot",
        })
    return {
        "datasets": datasets,
        "registry": stats,
        "data_origin": "local repository files",
        "upstream_fetch_performed": False,
    }


@app.get("/api/v1/bench/tasks", dependencies=[Depends(require_api_token)])
def bench_tasks(
    dataset: str = Query("livemcpbench", pattern="^(livemcpbench|mcptoolbenchpp)$"),
    q: str | None = Query(None, max_length=500),
    category: str | None = Query(None, max_length=100),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Browse benchmark task prompts without exposing gold tool labels to the analyst."""
    task_key = _BENCH_TASK_KEYS[dataset]
    all_tasks = _bench_data().get(task_key, [])
    filtered = all_tasks
    if category:
        filtered = [item for item in filtered if str(item.get("category", "")).casefold() == category.casefold()]
    if q:
        needle = q.casefold()
        filtered = [item for item in filtered if needle in str(item.get("query", "")).casefold()]
    page = filtered[offset:offset + limit]
    # Deliberately omit gold_tools and gold_unresolved. These belong to evaluation only.
    return {
        "dataset": dataset,
        "total": len(filtered),
        "offset": offset,
        "limit": limit,
        "tasks": [{
            "id": item.get("id"),
            "query": item.get("query", ""),
            "category": item.get("category", ""),
            "source": item.get("source", dataset),
            "n_steps": item.get("n_steps", 1),
        } for item in page],
        "gold_labels_exposed": False,
    }


@app.get("/api/v1/bench/tools", dependencies=[Depends(require_api_token)])
def bench_tools(
    source: str = Query("LiveMCPTool", pattern="^(LiveMCPTool|MCPToolBench\\+\\+|all)$"),
    q: str | None = Query(None, max_length=300),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Browse the retained tool registry; annotations remain metadata, not trusted evidence."""
    registry = _bench_data().get("registry", [])
    filtered = registry
    if source != "all":
        filtered = [item for item in filtered if item.get("source") == source]
    if q:
        needle = q.casefold()
        filtered = [item for item in filtered if needle in " ".join((
            str(item.get("server", "")), str(item.get("name", "")),
            str(item.get("description", "")),
        )).casefold()]
    page = filtered[offset:offset + limit]
    return {
        "source": source,
        "total": len(filtered),
        "offset": offset,
        "limit": limit,
        "tools": [{
            "id": item.get("id") or f'{item.get("server", "")}::{item.get("name", "")}',
            "server": item.get("server", ""),
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "input_schema": item.get("input_schema", {}),
            "output_schema": item.get("output_schema"),
            "annotations": item.get("annotations"),
            "source": item.get("source", ""),
            "category": item.get("category", ""),
            "definition_hash": item.get("hash"),
        } for item in page],
        "annotations_are_trusted_evidence": False,
    }


@app.post("/api/v1/discover", dependencies=[Depends(require_api_token)])
def discover(request: DiscoverRequest) -> dict[str, Any]:
    """Run TaaS discovery only; this endpoint does not invoke MCP tools."""
    validate_studio_goal_spec(request.goal_spec)
    profile = load_profile()
    raw_tools = [RawTool(**tool.model_dump()) for tool in request.tools]
    contracts = [extract_contract(tool) for tool in raw_tools]

    policy_data = request.policy
    try:
        policy = Policy.make(
            name=str(policy_data.get("name", "studio-default")),
            required=policy_data.get("required", []),
            allowed=policy_data.get("allowed", ["read(*)", "egress(*)", "session"]),
            lmin=policy_data.get("lmin", "obs"),
            forbidden=policy_data.get("forbidden", []),
            encoding=policy_data.get("encoding", "positive"),
        )
        engine_config = EngineConfig()
        for key, value in request.engine.items():
            if not hasattr(engine_config, key):
                raise ValueError(f"Unknown engine setting: {key}")
            setattr(engine_config, key, value)
        engine = DiscoveryEngine(
            contracts,
            profile,
            trust=DEFAULT_TRUST,
            cfg=engine_config,
        )
        # Preserve the natural-language prompt: the core parser accepts it as
        # a separate argument rather than reading goal_spec["prompt"] itself.
        parsed_spec = parse_studio_goal_spec(request.goal_spec)
        result = engine.discover(parsed_spec, policy)
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    certificate = result.certificate.to_dict() if result.certificate is not None else None
    counterexample = (
        result.counterexample.to_dict() if result.counterexample is not None else None
    )
    return {
        "status": "abstained" if result.abstained else "selected",
        "selected_tools": result.toolkit or [],
        # Return the canonical GoalSpec vocabulary accepted by parse_goal_spec.
        # Do not rename out/desc/deps/eff to presentation-only aliases.
        "goal_spec": {
            "prompt": result.spec.prompt,
            "prompt_inputs": [str(item) for item in result.spec.prompt_inputs],
            "goals": [
                {
                    "id": goal.id,
                    "class": goal.cls,
                    "in": [str(item) for item in goal.inputs],
                    "out": str(goal.out),
                    "eff": sorted(str(effect) for effect in goal.eff_plus),
                    "sigma": goal.sigma,
                    "sigma_reason": goal.sigma_reason,
                    "n": goal.n,
                    "exactness": goal.exactness,
                    "lang": goal.lang,
                    "deps": goal.deps,
                    "optional": goal.optional,
                    "desc": goal.desc,
                }
                for goal in result.spec.goals
            ],
        },
        "gap": [goal.id for goal in result.gap.gap],
        "rho": result.gap.rho,
        "certificate": certificate,
        "counterexample": counterexample,
        "composition": {
            "candidates": result.compose.candidates,
            "regime": result.compose.regime,
            "stats": result.compose.stats,
        },
        "discovery_time_seconds": result.time_s,
        "execution_performed": False,
        "model_profile": {
            "model_id": profile.model_id,
            "calibration": "configured" if os.environ.get("TAAS_MODEL_PROFILE") else "uncalibrated",
            "strict": profile.strict,
        },
    }


@app.get("/api/v1/models/runtime", dependencies=[Depends(require_api_token)])
def model_runtime_status() -> dict[str, Any]:
    """Report the actual process-local model state, not catalog metadata."""
    return get_model_runtime().status()


@app.post("/api/v1/models/load", dependencies=[Depends(require_api_token)])
def model_runtime_load(request: ModelLoadRequest) -> dict[str, Any]:
    """Explicitly download/load a selected HF model in this API process."""
    try:
        return get_model_runtime().load(request.model_id, request.device)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/models/chat", dependencies=[Depends(require_api_token)])
def model_runtime_chat(request: ModelChatRequest) -> dict[str, Any]:
    """Run a real inference request against the currently loaded model."""
    try:
        return get_model_runtime().chat(
            request.message, request.system, request.max_new_tokens, request.temperature
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/agents/decompose", dependencies=[Depends(require_api_token)])
def agent_decompose(request: AgentDecomposeRequest) -> dict[str, Any]:
    """Use the selected Studio model to propose a GoalSpec; validate separately."""
    try:
        result = get_model_runtime().decompose(
            request.prompt, request.context, request.max_new_tokens
        )
        if result.get("json_valid"):
            try:
                validate_studio_goal_spec(result["goal_spec"])
                result["structural_validation"] = {"valid": True}
            except HTTPException as exc:
                result["structural_validation"] = {"valid": False, "detail": exc.detail}
        else:
            result["structural_validation"] = {
                "valid": False,
                "detail": result.get("parse_error") or "Model did not return a canonical GoalSpec JSON object",
            }
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/agents/validate", dependencies=[Depends(require_api_token)])
def agent_manifest_validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a declarative Agent manifest without saving or executing it."""
    try:
        manifest = validate_agent_manifest(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    return {
        "valid": True,
        "manifest": manifest,
        "lifecycle_state": "draft",
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.post("/api/v1/agents", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_token)])
def agent_create(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a new immutable Agent version in draft state."""
    try:
        manifest = validate_agent_manifest(payload)
        resource = agent_registry.create_draft(manifest)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    except agent_registry.AgentRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Agent manifest must contain only strict JSON values") from exc
    return {
        **resource,
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.get("/api/v1/agents", dependencies=[Depends(require_api_token)])
def agent_list(agent_id: str | None = Query(default=None, max_length=63),
               limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return agent_registry.list_versions(agent_id=agent_id, limit=limit)


@app.get("/api/v1/agents/{agent_id}/versions/{version}", dependencies=[Depends(require_api_token)])
def agent_get(agent_id: str, version: str) -> dict[str, Any]:
    try:
        resource = agent_registry.get_version(agent_id, version)
    except agent_registry.AgentRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **resource,
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.post("/api/v1/agents/{agent_id}/versions/{version}/validate", dependencies=[Depends(require_api_token)])
def agent_validate_saved_version(agent_id: str, version: str) -> dict[str, Any]:
    """Revalidate stored bytes and advance draft -> validated; this is structural only."""
    try:
        resource = agent_registry.get_version(agent_id, version)
        manifest = validate_agent_manifest(resource["manifest"])
        if manifest != resource["manifest"]:
            raise HTTPException(status_code=409, detail="Stored Agent manifest is not canonical")
        resource = agent_registry.transition(agent_id, version, "validated")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    except agent_registry.AgentRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except agent_registry.AgentRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **resource,
        "validation_scope": "structural_schema_and_cross_field_invariants",
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.post("/api/v1/agents/{agent_id}/versions/{version}/publish", dependencies=[Depends(require_api_token)])
def agent_publish_version(
    agent_id: str,
    version: str,
    request: AgentPublishRequest | None = None,
) -> dict[str, Any]:
    """Publish configuration; tool grants must resolve against an immutable MCP snapshot."""
    try:
        current = agent_registry.get_version(agent_id, version)
        grants = current["manifest"]["spec"].get("tool_allowlist", [])
        snapshot_id = request.registry_snapshot_id if request else None
        resolved_grants = []
        if grants and not snapshot_id:
            raise HTTPException(
                status_code=422,
                detail="A read-only MCP registry snapshot is required to publish an Agent with tool grants",
            )
        if snapshot_id:
            snapshot = agent_registry.get_mcp_snapshot(snapshot_id)
            available = {}
            for server in snapshot["snapshot"].get("servers", []):
                for tool in server.get("tools", []):
                    available[(server.get("server_id"), tool.get("name"))] = tool.get("definition_sha256")
            missing = [
                {"server_id": grant["server_id"], "tool_name": grant["tool_name"]}
                for grant in grants
                if (grant["server_id"], grant["tool_name"]) not in available
            ]
            if missing:
                raise HTTPException(
                    status_code=409,
                    detail={"message": "Agent tool grants do not resolve in the selected MCP registry snapshot", "missing_grants": missing},
                )
            resolved_grants = [
                {
                    "server_id": grant["server_id"],
                    "tool_name": grant["tool_name"],
                    "tool_definition_sha256": available[(grant["server_id"], grant["tool_name"])],
                }
                for grant in grants
            ]
        resource = agent_registry.transition(
            agent_id, version, "published", registry_snapshot_id=snapshot_id
        )
    except agent_registry.AgentRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except agent_registry.AgentRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **resource,
        "published_as_configuration": True,
        "resolved_tool_grants": resolved_grants,
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.get("/api/v1/agents/events", dependencies=[Depends(require_api_token)])
def agent_events(agent_id: str | None = Query(default=None, max_length=63),
                 limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    return agent_registry.list_events(agent_id=agent_id, limit=limit)


@app.post("/api/v1/mcp/registry/snapshots/inspect", dependencies=[Depends(require_api_token)])
def mcp_registry_snapshot_inspect() -> dict[str, Any]:
    """Capture an immutable snapshot from operator-configured MCP servers using tools/list only."""
    try:
        configured = list_mcp_servers()
        if not configured.get("servers"):
            raise HTTPException(status_code=422, detail="No operator-configured MCP servers are available to inspect")
        servers = []
        for configured_server in sorted(configured["servers"], key=lambda item: item["id"]):
            inspected = inspect_mcp_server(configured_server["id"])
            if inspected.get("inspection_only") is not True or inspected.get("tool_execution_performed") is not False:
                raise HTTPException(status_code=502, detail=f"MCP inspection for {configured_server['id']} did not prove read-only behavior")
            if inspected.get("server_id") != configured_server["id"]:
                raise HTTPException(status_code=502, detail="MCP inspection returned a mismatched server identity")
            raw_tools = inspected.get("tools")
            if not isinstance(raw_tools, list) or len(raw_tools) > 500:
                raise HTTPException(status_code=502, detail=f"MCP server {configured_server['id']} returned an invalid or oversized tool list")
            normalized_tools = []
            seen = set()
            for tool in raw_tools:
                if not isinstance(tool, dict):
                    raise HTTPException(status_code=502, detail=f"MCP server {configured_server['id']} returned a malformed tool definition")
                if tool.get("server") not in (None, configured_server["id"]):
                    raise HTTPException(status_code=502, detail="MCP tool definition returned a mismatched server identity")
                name = tool.get("name")
                schema = tool.get("input_schema")
                if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", name):
                    raise HTTPException(status_code=502, detail=f"MCP server {configured_server['id']} returned an invalid tool name")
                if name in seen or not isinstance(schema, dict):
                    raise HTTPException(status_code=502, detail=f"MCP server {configured_server['id']} returned duplicate tools or an invalid input schema")
                seen.add(name)
                description = tool.get("description") or ""
                output_schema = tool.get("output_schema")
                annotations = tool.get("annotations")
                if not isinstance(description, str) or len(description) > 12000:
                    raise HTTPException(status_code=502, detail=f"MCP tool {name} returned an invalid description")
                if output_schema is not None and not isinstance(output_schema, dict):
                    raise HTTPException(status_code=502, detail=f"MCP tool {name} returned an invalid output schema")
                if annotations is not None and not isinstance(annotations, dict):
                    raise HTTPException(status_code=502, detail=f"MCP tool {name} returned invalid annotations")
                definition = {
                    "server_id": configured_server["id"],
                    "name": name,
                    "description": description,
                    "input_schema": schema,
                    "output_schema": output_schema,
                    "annotations": annotations,
                }
                canonical = json.dumps(definition, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                definition["definition_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                normalized_tools.append(definition)
            servers.append({
                "server_id": configured_server["id"],
                "server_name": inspected.get("server_name") or configured_server["name"],
                "server_info": inspected.get("server_info"),
                "protocol_version": inspected.get("protocol_version"),
                "tools": sorted(normalized_tools, key=lambda item: item["name"]),
                "inspection_only": True,
                "tool_execution_performed": False,
            })
        snapshot = {
            "schema_version": "taas.mcp.registry/v1",
            "capture_mode": "configured_stdio_tools_list",
            "servers": servers,
        }
        if sum(len(server["tools"]) for server in servers) > 5000:
            raise HTTPException(status_code=413, detail="MCP registry snapshot exceeds the 5,000-tool safety limit")
        try:
            snapshot_size = len(json.dumps(snapshot, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="MCP registry returned a non-JSON schema value") from exc
        if snapshot_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="MCP registry snapshot exceeds the 10 MiB safety limit")
        return agent_registry.store_mcp_snapshot(snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except MCPRegistryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/mcp/registry/snapshots", dependencies=[Depends(require_api_token)])
def mcp_registry_snapshots(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return agent_registry.list_mcp_snapshots(limit=limit)


@app.get("/api/v1/mcp/registry/snapshots/{snapshot_id}", dependencies=[Depends(require_api_token)])
def mcp_registry_snapshot_get(snapshot_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot_id):
        raise HTTPException(status_code=422, detail="snapshot_id must be a lowercase SHA-256 hex digest")
    try:
        return agent_registry.get_mcp_snapshot(snapshot_id)
    except agent_registry.AgentRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except agent_registry.AgentRegistryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/mcp/servers", dependencies=[Depends(require_api_token)])
def mcp_servers() -> dict[str, Any]:
    """List operator-configured MCP stdio servers without exposing commands or secrets."""
    try:
        return list_mcp_servers()
    except MCPRegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/mcp/servers/{server_id}/inspect", dependencies=[Depends(require_api_token)])
def mcp_inspect(server_id: str) -> dict[str, Any]:
    """Connect to a configured MCP server and list tool schemas; never calls tools."""
    try:
        return inspect_mcp_server(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MCPRegistryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.post(
    "/api/v1/agents/{agent_id}/versions/{version}/authorization/preflight",
    dependencies=[Depends(require_api_token)],
)
def agent_authorization_preflight(
    agent_id: str,
    version: str,
    request: AgentAuthorizationPreflightRequest,
) -> dict[str, Any]:
    """Evaluate trusted preconditions only; this route never authorizes or invokes tools."""
    try:
        agent = agent_registry.get_version(agent_id, version)
    except agent_registry.AgentRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    validate_studio_goal_spec(request.goal_spec)

    snapshot = None
    if agent.get("registry_snapshot_id"):
        try:
            snapshot = agent_registry.get_mcp_snapshot(agent["registry_snapshot_id"])
        except agent_registry.AgentRegistryError:
            snapshot = None

    trusted_config = None
    configuration_error = None
    try:
        trusted_config = load_trusted_authorization_config()
    except AuthorizationConfigurationError as exc:
        configuration_error = str(exc)

    try:
        return build_authorization_preflight(
            agent=agent,
            snapshot=snapshot,
            server_id=request.server_id,
            tool_name=request.tool_name,
            arguments=request.arguments,
            goal_spec=request.goal_spec,
            trusted_config=trusted_config,
            configuration_error=configuration_error,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def studio_home():
    """Serve the same-origin browser workspace."""
    from fastapi.responses import FileResponse

    page = Path(__file__).parent / "static" / "index.html"
    if not page.is_file():
        raise HTTPException(status_code=404, detail="Studio frontend is not installed")
    return FileResponse(page, media_type="text/html")
