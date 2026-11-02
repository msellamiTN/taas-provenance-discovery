"""Minimal HTTP boundary for the existing TaaS discovery core.

This is an experimental API, not a production-hardened multi-tenant service.
Protect it behind an authenticated tunnel/reverse proxy and keep it bound to loopback.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from taas.contracts import extract_contract
from taas.data.registries import RawTool
from taas.engine import DiscoveryEngine, EngineConfig
from taas.model_profile import EXTERNAL_CLASSES, MODEL_CLASSES, ModelProfile
from taas.goals import SIGMAS, parse_goal_spec
from taas.policy import Policy
from taas.provenance import DEFAULT_TRUST
from taas.studio.models import ModelCatalogError, get_model_details, search_models
from taas.studio.runtime import estimate_model_memory, probe_hardware

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


def validate_studio_goal_spec(spec: dict[str, Any]) -> None:
    """Fail early on the legacy/malformed UI payload instead of silently defaulting fields."""
    goals = spec.get("goals")
    if not isinstance(goals, list) or not goals:
        raise HTTPException(status_code=422, detail="goal_spec.goals must be a non-empty array")
    allowed_classes = set(MODEL_CLASSES) | set(EXTERNAL_CLASSES)
    legacy = {"output", "reason", "dependencies"}
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
        cls = goal.get("class")
        if cls not in allowed_classes:
            raise HTTPException(
                status_code=422,
                detail=f"{prefix}.class must be one of the supported model or external goal classes; got {cls!r}",
            )
        if not isinstance(goal.get("out"), str) or not goal["out"].strip():
            raise HTTPException(status_code=422, detail=f"{prefix}.out must be a semantic type string")
        if goal.get("sigma", "native") not in SIGMAS:
            raise HTTPException(status_code=422, detail=f"{prefix}.sigma must be one of {SIGMAS}")
        for field_name in ("in", "eff", "deps"):
            if field_name in goal and not isinstance(goal[field_name], list):
                raise HTTPException(status_code=422, detail=f"{prefix}.{field_name} must be an array")
        if any(not isinstance(item, str) for item in goal.get("in", []) + goal.get("eff", []) + goal.get("deps", [])):
            raise HTTPException(status_code=422, detail=f"{prefix}.in, eff and deps must contain strings")


def parse_studio_goal_spec(spec: dict[str, Any]):
    """Parse the core GoalSpec while preserving the Studio natural-language prompt."""
    return parse_goal_spec(spec, prompt=str(spec.get("prompt", "")))


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

@app.get("/", include_in_schema=False)
def studio_home():
    """Serve the same-origin browser workspace."""
    from fastapi.responses import FileResponse

    page = Path(__file__).parent / "static" / "index.html"
    if not page.is_file():
        raise HTTPException(status_code=404, detail="Studio frontend is not installed")
    return FileResponse(page, media_type="text/html")
