"""Minimal HTTP boundary for the existing TaaS discovery core.

This is an experimental API, not a production-hardened multi-tenant service.
Protect it behind an authenticated tunnel/reverse proxy and keep it bound to loopback.
"""
from __future__ import annotations

import copy
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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from taas.contracts import extract_contract
from taas.studio.discovery_diagnostics import build_discovery_diagnostics
from taas.effects import parse_effect
from taas.data.registries import RawTool, load_processed
from taas.engine import DiscoveryEngine, EngineConfig
from taas.model_profile import EXTERNAL_CLASSES, MODEL_CLASSES, ModelProfile
from taas.goals import SIGMAS, gap_analysis, parse_goal_spec
from taas.policy import Policy
from taas.provenance import DEFAULT_TRUST
from taas.studio.models import ModelCatalogError, get_model_details, inspect_model_artifacts, search_models
from taas.studio.agent_spec import validate_agent_manifest
from taas.studio.agent_context import build_agent_intelligence_context
from taas.studio.objective_traceability import build_objective_skill_traceability
from taas.studio import policy_engine
from taas.studio.tool_intelligence import build_tool_intelligence
from taas.studio import tool_registry
from taas.studio import tool_service
from taas.studio.agent_skill_bindings import (
    AgentSkillBindingConflict,
    AgentSkillBindingError,
    AgentSkillBindingNotFound,
    resolve_agent_skill_references,
)
from taas.studio import agent_registry
from taas.studio import skill_registry
from taas.studio import skill_dependency_graph
from taas.studio import assurance_evidence
from taas.studio.skill_spec import validate_skill_manifest
from taas.studio import release_readiness
from taas.studio import assurance_evidence
from taas.studio.authorization_preflight import (
    AuthorizationConfigurationError,
    build_authorization_preflight,
    load_trusted_authorization_config,
)
from taas.studio.runtime import estimate_model_memory, probe_hardware, probe_runtime
from taas.studio.model_runtime import ModelRuntimeError, get_model_runtime
from taas.studio.analyst_contract import validate_theta_types, build_refinement_context, load_analyst_contract
from taas.studio.objective_contract import (build_objective_context, derive_objective_contract, diagnose_objective_alignment, build_outcome_coverage)
from taas.studio.objective_contract_v3 import derive_objective_contract_v3, validate_objective_contract_v3
from taas.studio.ollama_runtime import get_ollama_runtime
from taas.studio.mcp_registry import MCPRegistryError, inspect_server as inspect_mcp_server, list_servers as list_mcp_servers
from taas.types import KINDS
from taas.studio.assurance_routes import build_assurance_router
from taas.hypergraph_projection import (
    project_hypergraph,
    project_objective_skill_traceability,
    project_skill_dependency_graph,
)

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
    tools: list[ToolInput] = Field(default_factory=list, max_length=500)
    registry_tool_ids: list[str] = Field(default_factory=list, max_length=500)
    provider: str = Field(default="huggingface", pattern="^(huggingface|ollama)$")
    model_id: str | None = Field(default=None, min_length=3, max_length=257)
    human_review_confirmed: bool = False
    policy: dict[str, Any] = Field(default_factory=dict)
    engine: dict[str, Any] = Field(default_factory=dict)


class ModelLoadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(min_length=3, max_length=257)
    provider: str = Field(default="huggingface", pattern="^(huggingface|ollama)$")
    device: str = Field(default="auto", pattern="^(auto|cpu|cuda)$")


class ModelChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="huggingface", pattern="^(huggingface|ollama)$")
    message: str = Field(min_length=1, max_length=12000)
    system: str = Field(default="You are a helpful assistant.", max_length=4000)
    max_new_tokens: int = Field(default=512, ge=1, le=2048)
    temperature: float = Field(default=0.2, ge=0, le=2)


class AgentDecomposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="huggingface", pattern="^(huggingface|ollama)$")
    prompt: str = Field(min_length=1, max_length=12000)
    context: str = Field(default="", max_length=8000)
    max_new_tokens: int = Field(default=1200, ge=1, le=2048)
    agent_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{2,62}$")
    agent_version: str | None = Field(default=None, pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")

    @model_validator(mode="after")
    def require_agent_reference_pair(self):
        if (self.agent_id is None) != (self.agent_version is None):
            raise ValueError("agent_id and agent_version must be supplied together")
        return self


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


def classify_core_gap_requirements(goals: list[Any], gap_goal_ids: list[str]) -> dict[str, Any]:
    """Separate external tool requirements from uncovered model-native capabilities.

    This is a presentation/diagnostic classification only: it does not change
    gap_analysis, model rho, eligibility, discovery, or execution authorization.
    """
    gap_ids = set(gap_goal_ids)
    tool_required = [
        str(goal.id) for goal in goals
        if str(goal.id) in gap_ids and str(goal.cls) in EXTERNAL_CLASSES
    ]
    model_capability_gaps = [
        str(goal.id) for goal in goals
        if str(goal.id) in gap_ids and str(goal.cls) not in EXTERNAL_CLASSES
    ]
    if tool_required and model_capability_gaps:
        status = "tool_and_model_capability_gaps_detected"
    elif tool_required:
        status = "tool_requirements_detected"
    elif model_capability_gaps:
        status = "capability_gap_detected"
    else:
        status = "model_coverage_candidate"
    return {
        "status": status,
        "tool_required_goal_ids": tool_required,
        "model_capability_gap_goal_ids": model_capability_gaps,
    }



def resolve_agent_skill_bindings_or_http(manifest: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Resolve exact published Skill versions; references are guidance, never grants."""
    try:
        return resolve_agent_skill_references(manifest)
    except AgentSkillBindingNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentSkillBindingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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


def canonicalize_declared_plural_types(spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Canonicalize only a trailing plural 's' when the singular type is explicitly in Θ.

    This is a narrow schema-backed spelling repair (e.g. records[] -> record[]),
    not domain inference or a relaxation of the semantic type vocabulary.
    """
    candidate = copy.deepcopy(spec)
    try:
        _, theta = load_analyst_contract()
    except RuntimeError:
        return candidate, []
    allowed = set(theta.get("common_types", []))
    events: list[dict[str, str]] = []

    def canonicalize(value: Any, path: str) -> Any:
        if not isinstance(value, str) or not value.endswith("[]"):
            return value
        body = value[:-2]
        if not body.endswith("s"):
            return value
        singular = body[:-1] + "[]"
        if singular not in allowed:
            return value
        events.append({"path": path, "from": value, "to": singular,
                       "rule": "trailing_plural_s_to_declared_theta_type"})
        return singular

    prompt_inputs = candidate.get("prompt_inputs")
    if isinstance(prompt_inputs, list):
        candidate["prompt_inputs"] = [
            canonicalize(value, f"prompt_inputs[{index}]")
            for index, value in enumerate(prompt_inputs)
        ]
    goals = candidate.get("goals")
    if isinstance(goals, list):
        for index, goal in enumerate(goals):
            if not isinstance(goal, dict):
                continue
            if "out" in goal:
                goal["out"] = canonicalize(goal["out"], f"goals[{index}].out")
            inputs = goal.get("in")
            if isinstance(inputs, list):
                goal["in"] = [
                    canonicalize(value, f"goals[{index}].in[{position}]")
                    for position, value in enumerate(inputs)
                ]
    return candidate, events


def canonicalize_retrieval_target_inputs(
    spec: dict[str, Any],
    objective_contract: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove a retrieved-record target incorrectly emitted as a user/source input.

    This narrow repair applies only when the Objective Contract says source data
    is required but no user-supplied content is expected, and a retrieve goal
    labels its input with an undeclared collection placeholder ending in
    '_records' (or exactly 'records'). The retrieved collection remains the
    goal output and its business concept remains in the authored description.
    No schema/domain is inferred; the event is retained for human review.
    """
    candidate = copy.deepcopy(spec)
    constraints = objective_contract.get("constraints") if isinstance(objective_contract, dict) else None
    inputs_contract = constraints.get("inputs") if isinstance(constraints, dict) else None
    if not isinstance(inputs_contract, dict):
        return candidate, []
    if inputs_contract.get("source_data_required") is not True or inputs_contract.get("user_supplied_content") is not False:
        return candidate, []

    try:
        _, theta = load_analyst_contract()
    except RuntimeError:
        return candidate, []
    allowed_types = set(theta.get("common_types", []))
    if "record[]" not in allowed_types:
        return candidate, []

    def is_retrieved_collection_placeholder(value: Any) -> bool:
        return (
            isinstance(value, str)
            and value not in allowed_types
            and (value == "records" or bool(re.fullmatch(r"[a-z][a-z0-9_]*_records", value)))
        )

    goals = candidate.get("goals")
    if not isinstance(goals, list):
        return candidate, []
    removed_values: set[str] = set()
    events: list[dict[str, Any]] = []
    for index, goal in enumerate(goals):
        if not isinstance(goal, dict) or goal.get("class") != "retrieve":
            continue
        values = goal.get("in")
        if not isinstance(values, list):
            continue
        removed = [value for value in values if is_retrieved_collection_placeholder(value)]
        if not removed:
            continue
        goal["in"] = [value for value in values if value not in removed]
        removed_values.update(removed)
        events.append({
            "path": f"goals[{index}].in",
            "from": copy.deepcopy(values),
            "to": copy.deepcopy(goal["in"]),
            "removed": copy.deepcopy(removed),
            "rule": "retrieved_collection_is_output_not_source_input",
            "reason": (
                "The Objective Contract requires configured source data and states that no user-supplied "
                "content is expected. The retrieved collection is represented by the retrieve goal output; "
                "its business concept remains in the goal description."
            ),
        })

    prompt_inputs = candidate.get("prompt_inputs")
    if isinstance(prompt_inputs, list) and removed_values:
        removed_prompt_inputs = [
            value for value in prompt_inputs
            if isinstance(value, str) and value in removed_values
        ]
        if removed_prompt_inputs:
            candidate["prompt_inputs"] = [
                value for value in prompt_inputs if value not in removed_prompt_inputs
            ]
            events.append({
                "path": "prompt_inputs",
                "from": copy.deepcopy(prompt_inputs),
                "to": copy.deepcopy(candidate["prompt_inputs"]),
                "removed": copy.deepcopy(removed_prompt_inputs),
                "rule": "retrieved_collection_is_output_not_user_prompt_input",
                "reason": (
                    "The Objective Contract states that the source data is not user-supplied. "
                    "The retrieved collection is therefore not a prompt input type."
                ),
            })
    return candidate, events


def canonicalize_arithmetic_expressions_from_effects(
    spec: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove arithmetic expressions mistakenly placed in the effect vocabulary.

    GoalSpec effects encode boundary side effects (read/write/delete/egress/exec/
    money/session), not the mathematical operation performed by a model-side
    aggregate. This narrowly recognizes arithmetic expressions only on
    aggregate/compute_exact/count goals. It does not validate the formula or
    infer its fields; raw model output and the exact removed expression remain
    available in provenance for human review.
    """
    candidate = copy.deepcopy(spec)
    goals = candidate.get("goals")
    if not isinstance(goals, list):
        return candidate, []

    arithmetic_functions = {"sum", "count", "avg", "mean", "min", "max"}
    token_pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*|[0-9]+(?:[.][0-9]+)?|[()+*/%,+-]")
    events: list[dict[str, Any]] = []

    def is_arithmetic_expression(value: Any) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False
        compact = re.sub(r"\s+", "", value)
        tokens = token_pattern.findall(value)
        if not tokens or "".join(tokens) != compact:
            return False
        if not any(token in {"+", "-", "*", "/"} for token in tokens) and not any(
            tokens[i] in arithmetic_functions and i + 1 < len(tokens) and tokens[i + 1] == "("
            for i in range(len(tokens))
        ):
            return False
        depth = 0
        for index, token in enumerate(tokens):
            if token == "(":
                depth += 1
                if index == 0 or tokens[index - 1] not in arithmetic_functions:
                    # Parentheses may group arithmetic, but not invoke an unknown function.
                    if index == 0 or tokens[index - 1] not in {"+", "-", "*", "/", "("}:
                        return False
            elif token == ")":
                depth -= 1
                if depth < 0:
                    return False
        return depth == 0

    for index, goal in enumerate(goals):
        if not isinstance(goal, dict) or goal.get("class") not in {
            "aggregate", "compute_exact", "count"
        }:
            continue
        effects = goal.get("eff")
        if not isinstance(effects, list):
            continue
        removed = [effect for effect in effects if is_arithmetic_expression(effect)]
        if not removed:
            continue
        goal["eff"] = [effect for effect in effects if effect not in removed]
        events.append({
            "path": f"goals[{index}].eff",
            "from": copy.deepcopy(effects),
            "to": copy.deepcopy(goal["eff"]),
            "removed": copy.deepcopy(removed),
            "rule": "arithmetic_expression_misplaced_in_effects",
            "reason": (
                "GoalSpec effects encode boundary side effects, not arithmetic expressions. "
                "The expression is retained in normalization provenance and the raw model output; "
                "its mathematical correctness and field assumptions are not validated by this repair."
            ),
        })
    return candidate, events


def canonicalize_self_dependencies(
    spec: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove impossible self-edges from the GoalSpec DAG with explicit provenance."""
    candidate = copy.deepcopy(spec)
    goals = candidate.get("goals")
    if not isinstance(goals, list):
        return candidate, []
    events: list[dict[str, Any]] = []
    for index, goal in enumerate(goals):
        if not isinstance(goal, dict) or not isinstance(goal.get("id"), str):
            continue
        deps = goal.get("deps")
        if not isinstance(deps, list):
            continue
        removed = [dep for dep in deps if dep == goal["id"]]
        if not removed:
            continue
        remaining = [dep for dep in deps if dep != goal["id"]]
        goal["deps"] = remaining
        events.append({
            "path": f"goals[{index}].deps",
            "from": copy.deepcopy(deps),
            "to": copy.deepcopy(remaining),
            "removed": copy.deepcopy(removed),
            "rule": "self_dependency_removed",
            "reason": (
                "A GoalSpec dependency must reference a distinct prerequisite goal. "
                "Self-dependencies are invalid DAG edges and cannot express a valid prerequisite."
            ),
        })
    return candidate, events


def canonicalize_single_goal_input_dependencies(
    spec: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove only input-name pseudo-edges from a one-goal candidate, with provenance.

    A GoalSpec dependency is an edge to another goal ID. In a one-goal graph,
    a declared input name cannot identify a distinct prerequisite goal. This
    narrowly repairs that namespace collision; all other dependency values and
    all multi-goal graphs are left untouched for strict validation.
    """
    candidate = copy.deepcopy(spec)
    goals = candidate.get("goals")
    if not isinstance(goals, list) or len(goals) != 1 or not isinstance(goals[0], dict):
        return candidate, []

    goal = goals[0]
    deps = goal.get("deps")
    if not isinstance(deps, list) or not deps:
        return candidate, []

    input_names: set[str] = set()
    for field in ("in",):
        values = goal.get(field)
        if isinstance(values, list):
            input_names.update(value for value in values if isinstance(value, str))
    prompt_inputs = candidate.get("prompt_inputs")
    if isinstance(prompt_inputs, list):
        input_names.update(value for value in prompt_inputs if isinstance(value, str))

    goal_id = goal.get("id")
    removable = [
        dep for dep in deps
        if isinstance(dep, str) and dep != goal_id and dep in input_names
    ]
    if not removable:
        return candidate, []

    remaining = [dep for dep in deps if dep not in removable]
    goal["deps"] = remaining
    event = {
        "path": "goals[0].deps",
        "from": copy.deepcopy(deps),
        "to": copy.deepcopy(remaining),
        "removed": copy.deepcopy(removable),
        "rule": "single_goal_input_name_not_dependency",
        "reason": (
            "A dependency must reference another goal ID; this one-goal candidate "
            "declared the removed value as an input name, not as a goal."
        ),
    }
    return candidate, [event]


def canonicalize_objective_constraint_dependencies(
    spec: dict[str, Any],
    objective_contract: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove dependency entries that name Objective Contract constraints, not goals.

    GoalSpec deps are graph edges and may reference only declared goal IDs. Objective
    Contract constraints live in a separate namespace. This repair is exact-name,
    contract-backed, provenance-recorded, and never removes a dependency that is a
    declared goal ID.
    """
    candidate = copy.deepcopy(spec)
    constraints = objective_contract.get("constraints") if isinstance(objective_contract, dict) else None
    if not isinstance(constraints, dict):
        return candidate, []

    constraint_names: set[str] = set()
    def collect_names(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if isinstance(key, str) and not isinstance(nested, (dict, list)):
                    constraint_names.add(key)
                collect_names(nested)
        elif isinstance(value, list):
            for nested in value:
                collect_names(nested)
    collect_names(constraints)

    goals = candidate.get("goals")
    if not isinstance(goals, list):
        return candidate, []
    goal_ids = {
        goal.get("id") for goal in goals
        if isinstance(goal, dict) and isinstance(goal.get("id"), str)
    }
    events: list[dict[str, Any]] = []
    for index, goal in enumerate(goals):
        if not isinstance(goal, dict):
            continue
        deps = goal.get("deps")
        if not isinstance(deps, list) or not deps:
            continue
        removed = [
            dep for dep in deps
            if isinstance(dep, str) and dep not in goal_ids and dep in constraint_names
        ]
        if not removed:
            continue
        remaining = [dep for dep in deps if dep not in removed]
        goal["deps"] = remaining
        events.append({
            "path": f"goals[{index}].deps",
            "from": copy.deepcopy(deps),
            "to": copy.deepcopy(remaining),
            "removed": copy.deepcopy(removed),
            "rule": "objective_constraint_name_not_goal_dependency",
            "reason": (
                "The removed value names an Objective Contract constraint, not a GoalSpec goal ID. "
                "The constraint remains preserved in the Objective Contract."
            ),
        })
    return candidate, events


def prepare_agent_candidate(
    candidate: dict[str, Any],
    original_objective: str,
    objective_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preserve the objective and apply only narrow, provenance-recorded canonicalizations."""
    prepared = copy.deepcopy(candidate)
    spec = prepared.get("goal_spec")
    if isinstance(spec, dict):
        normalized, type_events = canonicalize_declared_plural_types(spec)
        normalized, retrieval_input_events = canonicalize_retrieval_target_inputs(
            normalized, objective_contract
        )
        normalized, self_dependency_events = canonicalize_self_dependencies(normalized)
        normalized, arithmetic_effect_events = canonicalize_arithmetic_expressions_from_effects(normalized)
        normalized, input_dependency_events = canonicalize_single_goal_input_dependencies(normalized)
        normalized, constraint_dependency_events = canonicalize_objective_constraint_dependencies(
            normalized, objective_contract
        )
        # The objective is user-authored input, not a field the model may truncate,
        # paraphrase, or replace. Keep the model's raw response in prepared["text"].
        normalized["prompt"] = original_objective
        prepared["goal_spec"] = normalized
        prepared["normalization_events"] = (
            type_events + retrieval_input_events + self_dependency_events
            + arithmetic_effect_events + input_dependency_events + constraint_dependency_events
        )
        prepared["objective_prompt_preserved"] = True
    return prepared


def validate_studio_goal_spec(spec: dict[str, Any]) -> None:
    """Fail early on the legacy/malformed UI payload instead of silently defaulting fields."""
    goals = spec.get("goals")
    if not isinstance(goals, list) or not goals:
        raise HTTPException(status_code=422, detail="goal_spec.goals must be a non-empty array")
    allowed_classes = set(MODEL_CLASSES) | set(EXTERNAL_CLASSES)
    legacy = {"output", "reason", "dependencies"}
    ids: list[str] = []
    type_pattern = re.compile(r"^([a-z_]+)(?::[a-z0-9_-]+)?(\[\])?$")
    try:
        _, theta_vocabulary = load_analyst_contract()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    theta_domains = set(theta_vocabulary.get("domains", []))
    theta_types = set(theta_vocabulary.get("common_types", []))

    def valid_semantic_type(value: str) -> bool:
        match = type_pattern.fullmatch(value)
        return bool(match and match.group(1) in KINDS and value in theta_types)

    def invalid_type_detail(path: str, value: str) -> str:
        if value in theta_domains:
            return (
                f"{path} uses domain label {value!r} where a semantic type is required. "
                f"A domain is not a kind: use a declared kind-qualified type if available, "
                "or 'text' for a natural-language prompt input. Resolve collection shape "
                "against Θ.common_types; a domain name alone is not a semantic type."
            )
        if isinstance(value, str):
            if path == "goal_spec.prompt_inputs":
                return (
                    f"{path} contains invalid semantic type {value!r}; expected a declared semantic type string. "
                    "Use an exact entry from Θ.common_types."
                )
            return (
                f"{path} uses an undeclared Θ semantic type string {value!r}; it is syntactically valid "
                "but absent from Θ.common_types. For an unresolved collection, use 'record[]' "
                "and preserve the business concept in the goal description."
            )
        if path == "goal_spec.prompt_inputs":
            return (f"{path} contains invalid semantic type {value!r}; prompt_inputs must be a semantic type string. "
                    "Use a declared Θ kind with an optional declared domain.")
        return f"{path} must be a semantic type string; got invalid value {value!r}. Use a declared Θ kind with an optional declared domain."

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
            raise HTTPException(status_code=422, detail=invalid_type_detail(f"{prefix}.out", str(out_type)))
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
                raise HTTPException(status_code=422, detail=invalid_type_detail(f"{prefix}.in", input_type))
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
            raise HTTPException(status_code=422, detail=invalid_type_detail("goal_spec.prompt_inputs", item))
    if "prompt" in spec and not isinstance(spec["prompt"], str):
        raise HTTPException(status_code=422, detail="goal_spec.prompt must be a string")
    known_ids = set(ids)
    for index, goal in enumerate(goals):
        for dep in goal.get("deps", []):
            if dep not in known_ids:
                raise HTTPException(status_code=422, detail=f"goal {ids[index]} references unknown dependency {dep!r}")
            if dep == ids[index]:
                raise HTTPException(status_code=422, detail=f"goal {ids[index]} cannot depend on itself")
    theta_error = validate_theta_types(spec)
    if theta_error:
        raise HTTPException(status_code=422, detail=theta_error)
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


@app.get("/api/v1/tools", dependencies=[Depends(require_api_token)])
def tool_registry_search(
    q: str | None = Query(None, max_length=300),
    server: str | None = Query(None, max_length=128),
    source: str | None = Query(None, max_length=64),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Search retained-registry tool identities with definition-hash pins."""
    return tool_registry.search_registry_tools(
        q=q, server=server, source=source, offset=offset, limit=limit
    )


@app.get("/api/v1/tools/{server}/{name}", dependencies=[Depends(require_api_token)])
def tool_registry_resolve(server: str, name: str) -> dict[str, Any]:
    """Resolve one exact server::name tool; verify its stored definition hash."""
    identity = tool_registry.resolve_registry_tool(server, name)
    if identity is None:
        raise HTTPException(status_code=404, detail=f"Unknown registry tool: {server}::{name}")
    return identity


def _tool_attestation_lookup(binding: dict[str, Any]) -> dict[str, Any]:
    return assurance_evidence.list_verified_evidence_for_subject(binding)


@app.get("/api/v1/tools/{server}/{name}/intelligence", dependencies=[Depends(require_api_token)])
def tool_capability_intelligence(server: str, name: str) -> dict[str, Any]:
    """Structured capability profile with declared/observed/attested evidence axis."""
    profile = tool_registry.build_capability_profile(
        server, name, attestation_lookup=_tool_attestation_lookup
    )
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Unknown registry tool: {server}::{name}")
    return profile


class ToolRetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=2000)
    goal_out: str | None = Field(default=None, max_length=128)
    k: int = Field(default=10, ge=1, le=32)
    components: list[str] | None = Field(default=None, max_length=3)
    type_filter: bool = True
    prompt_inputs: list[str] = Field(default_factory=list, max_length=32)
    include_hypergraph: bool = False
    policy: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/v1/tools/retrieve", dependencies=[Depends(require_api_token)])
def tool_retrieve(request: ToolRetrieveRequest) -> dict[str, Any]:
    """Goal-oriented hybrid retrieval over the registry with score explanation."""
    policy_data = request.policy
    try:
        policy = Policy.make(
            name=str(policy_data.get("name", "tool-intelligence")),
            required=policy_data.get("required", []),
            allowed=policy_data.get("allowed", ["read(*)", "egress(*)", "session"]),
            lmin=policy_data.get("lmin", "obs"),
            forbidden=policy_data.get("forbidden", []),
            encoding=policy_data.get("encoding", "positive"),
        )
        return tool_service.explainable_retrieve(
            request.query, request.goal_out,
            policy=policy, k=request.k, components=request.components,
            type_filter=request.type_filter, prompt_inputs=request.prompt_inputs,
            include_hypergraph=request.include_hypergraph,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class ToolEligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_ids: list[str] | None = Field(default=None, max_length=64)
    policy: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/v1/tools/eligibility", dependencies=[Depends(require_api_token)])
def tool_eligibility(request: ToolEligibilityRequest) -> dict[str, Any]:
    """Explain policy eligibility/rejection per tool with evidence strengths."""
    policy_data = request.policy
    try:
        policy = Policy.make(
            name=str(policy_data.get("name", "tool-intelligence")),
            required=policy_data.get("required", []),
            allowed=policy_data.get("allowed", ["read(*)", "egress(*)", "session"]),
            lmin=policy_data.get("lmin", "obs"),
            forbidden=policy_data.get("forbidden", []),
            encoding=policy_data.get("encoding", "positive"),
            visible=(frozenset(policy_data["visible"]) if policy_data.get("visible") else None),
        )
        return tool_service.eligibility_explain(policy, request.tool_ids)
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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



@app.post("/api/v1/objectives/discover", dependencies=[Depends(require_api_token)])
@app.post("/api/v1/discover", dependencies=[Depends(require_api_token)], include_in_schema=False)
def discover(request: DiscoverRequest) -> dict[str, Any]:
    """Run TaaS discovery only; this endpoint does not invoke MCP tools."""
    if not request.human_review_confirmed:
        raise HTTPException(
            status_code=409,
            detail="Human review is required for the objective-to-GoalSpec mapping and selected tool metadata before discovery.",
        )
    validate_studio_goal_spec(request.goal_spec)
    objective = str(request.goal_spec.get("prompt", "")).strip()
    if not objective:
        raise HTTPException(
            status_code=422,
            detail="goal_spec.prompt must preserve the original natural-language objective for Core conformance validation.",
        )
    objective_diagnostics = diagnose_objective_alignment(objective, request.goal_spec)
    objective_errors = [item for item in objective_diagnostics if item.get("severity") == "error"]
    if objective_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "TaaS Core objective conformance rejected this GoalSpec; discovery was not started.",
                "diagnostics": objective_diagnostics,
            },
        )
    configured_profile = load_profile()
    profile_matches = bool(
        request.model_id and configured_profile.model_id == request.model_id
    )
    if request.model_id and not profile_matches:
        profile = ModelProfile(model_id=request.model_id, strict=True)
    else:
        profile = configured_profile
    if request.tools and request.registry_tool_ids:
        raise HTTPException(
            status_code=422,
            detail="Supply either tools or registry_tool_ids, not both.",
        )
    if request.registry_tool_ids:
        raw_tools = []
        unresolved = []
        for tool_id in request.registry_tool_ids:
            if "::" not in tool_id:
                unresolved.append(tool_id)
                continue
            raw = tool_registry._raw_tools().get(tool_id)
            if raw is None:
                unresolved.append(tool_id)
            else:
                raw_tools.append(raw)
        if unresolved:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "registry_tool_ids must resolve to exact server::name registry tools",
                    "unresolved": unresolved,
                },
            )
    else:
        raw_tools = [RawTool(**tool.model_dump()) for tool in request.tools]
    if not raw_tools:
        raise HTTPException(
            status_code=422,
            detail="Discovery requires at least one tool (tools or registry_tool_ids).",
        )
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
    discovery_diagnostics = build_discovery_diagnostics(
        engine, policy, result.compose.stats, result.toolkit, result.abstained
    )
    reachability = getattr(result.compose, "reachability", None)
    hypergraph_projection = None
    projection_status = "unavailable_abstained"
    if not result.abstained and reachability is not None:
        # Projection consumes the server-owned graph and final core ReachResult.
        # It is a read-only view; no graph semantics are recomputed here.
        hypergraph_projection = project_hypergraph(
            engine.H,
            reachability,
            model_edges=engine.composer.model_edges(result.spec.goals),
        )
        projection_status = "available"
    counterexample = (
        result.counterexample.to_dict() if result.counterexample is not None else None
    )
    return {
        "status": "abstained" if result.abstained else "selected",
        "tool_source": "registry_tool_ids" if request.registry_tool_ids else "request_tools",
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
        "discovery_diagnostics": discovery_diagnostics,
        "tool_intelligence": build_tool_intelligence(
            contracts=getattr(engine.H, "contracts", {}) or {},
            diagnostics=discovery_diagnostics,
            goals=list(result.spec.goals),
            toolkit=result.toolkit,
            certificate=certificate,
        ),
        "discovery_time_seconds": result.time_s,
        "hypergraph_projection_status": projection_status,
        "hypergraph_projection": hypergraph_projection,
        "execution_performed": False,
        "human_review": {"confirmed": True, "scope": "goal_spec_and_selected_tool_metadata",
                         "semantic_correctness_verified": False},
        "objective_conformance": {"accepted_for_human_review": True,
                                  "diagnostics": objective_diagnostics,
                                  "semantic_correctness_verified": False},
        "model_profile": {
            "provider": request.provider,
            "model_id": profile.model_id,
            "requested_model_id": request.model_id,
            "calibrated_profile_matched": profile_matches,
            "calibration": "configured" if (not request.model_id or profile_matches) and os.environ.get("TAAS_MODEL_PROFILE") else "uncalibrated",
            "strict": profile.strict,
        },
    }


@app.get("/api/v1/models/runtime", dependencies=[Depends(require_api_token)])
def model_runtime_status() -> dict[str, Any]:
    """Report runtime state for both configured inference providers."""
    state = get_model_runtime().status()
    state["providers"] = {
        "huggingface": {"supported": True, "model_loaded": state.get("model_loaded", False),
                        "model_id": state.get("model_id"), "device": state.get("device")},
        "ollama": get_ollama_runtime().status(),
    }
    return state


@app.post("/api/v1/models/load", dependencies=[Depends(require_api_token)])
def model_runtime_load(request: ModelLoadRequest) -> dict[str, Any]:
    """Explicitly download/load a selected HF model in this API process."""
    try:
        if request.provider == "ollama":
            if request.device != "auto":
                raise ValueError("Ollama manages device placement; omit device or use auto")
            return get_ollama_runtime().load(request.model_id)
        return get_model_runtime().load(request.model_id, request.device)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/models/chat", dependencies=[Depends(require_api_token)])
def model_runtime_chat(request: ModelChatRequest) -> dict[str, Any]:
    """Run a real inference request against the currently loaded model."""
    try:
        runtime = get_ollama_runtime() if request.provider == "ollama" else get_model_runtime()
        return runtime.chat(request.message, request.system, request.max_new_tokens, request.temperature)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/objectives/prepare", dependencies=[Depends(require_api_token)])
@app.post("/api/v1/agents/decompose", dependencies=[Depends(require_api_token)], include_in_schema=False)
def agent_decompose(request: AgentDecomposeRequest) -> dict[str, Any]:
    """Use the selected Studio model to propose a GoalSpec; validate separately."""
    try:
        runtime = get_ollama_runtime() if request.provider == "ollama" else get_model_runtime()
        # TaaS Core contributes an objective frame before generation. The model is
        # not given the MCP registry; capability matching remains a later Core stage.
        objective_contract = derive_objective_contract(request.prompt)
        objective_contract_v3 = derive_objective_contract_v3(request.prompt)
        objective_contract_v3_errors = validate_objective_contract_v3(objective_contract_v3)
        objective_context = build_objective_context(request.prompt)
        base_context = request.context.strip()
        if base_context:
            base_context += "\n\n"
        base_context += objective_context
        agent_context = None
        agent_context_trace = {
            "schema": "taas.agent-intelligence-context/v1",
            "status": "not_configured",
            "instructions_injected": False,
            "skills": [],
            "selected_skill_ids": [],
            "context_authority": "guidance_only_core_contract_and_governance_remain_authoritative",
        }
        if request.agent_id and request.agent_version:
            try:
                saved_agent = agent_registry.get_version(request.agent_id, request.agent_version)
            except agent_registry.AgentRegistryNotFound as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            manifest = validate_agent_manifest(saved_agent["manifest"])
            manifest, external_skill_references = resolve_agent_skill_bindings_or_http(manifest)
            agent_context, agent_context_trace = build_agent_intelligence_context(
                manifest,
                request.prompt,
                manifest_sha256=saved_agent.get("manifest_sha256"),
                lifecycle_state=saved_agent.get("lifecycle_state"),
            )
            agent_context_trace["external_skill_references"] = external_skill_references
            external_by_id = {item["id"]: item for item in external_skill_references}
            for skill_trace in agent_context_trace.get("skills", []):
                external = external_by_id.get(skill_trace.get("id"))
                if external:
                    skill_trace["source"] = "skill_registry"
                    skill_trace["registry_manifest_sha256"] = external["manifest_sha256"]
        if agent_context is None:
            # Preserve the legacy runtime call contract for callers without an Agent binding.
            result = runtime.decompose(request.prompt, base_context, request.max_new_tokens)
        else:
            result = runtime.decompose(
                request.prompt, base_context, request.max_new_tokens,
                agent_context=agent_context,
            )
        result = prepare_agent_candidate(result, request.prompt, objective_contract)

        def assess(candidate: dict[str, Any]) -> tuple[bool, list[dict[str, str]], Any]:
            structural_error: Any = None
            if candidate.get("json_valid") and isinstance(candidate.get("goal_spec"), dict):
                try:
                    validate_studio_goal_spec(candidate["goal_spec"])
                except HTTPException as exc:
                    structural_error = exc.detail
            else:
                structural_error = candidate.get("parse_error") or "Model did not return a canonical GoalSpec JSON object"
            # One canonical semantic validator owns Studio acceptance. Provider-
            # local heuristics may be returned for diagnostics, but cannot override Core.
            diagnostics: list[dict[str, str]] = []
            if candidate.get("json_valid") and isinstance(candidate.get("goal_spec"), dict):
                diagnostics = diagnose_objective_alignment(request.prompt, candidate["goal_spec"])
            for event in candidate.get("normalization_events", []):
                if event.get("rule") == "trailing_plural_s_to_declared_theta_type":
                    diagnostics.append({
                        "code": "declared_plural_type_normalized",
                        "severity": "warning",
                        "message": f"{event['path']}: normalized {event['from']!r} to declared Θ type {event['to']!r}.",
                        "suggestion": "Review the canonical type; no undeclared type or business domain was inferred.",
                    })
                elif event.get("rule") == "single_goal_input_name_not_dependency":
                    diagnostics.append({
                        "code": "single_goal_input_dependency_canonicalized",
                        "severity": "warning",
                        "message": (
                            f"{event['path']}: removed input-name value(s) {event['removed']!r} "
                            "from a single-goal dependency list; raw model output is retained."
                        ),
                        "suggestion": (
                            "Review this explicit canonicalization. Goal dependencies must reference "
                            "other goal IDs; this one-goal candidate has no distinct prerequisite goal."
                        ),
                    })
                elif event.get("rule") in (
                    "retrieved_collection_is_output_not_source_input",
                    "retrieved_collection_is_output_not_user_prompt_input",
                ):
                    diagnostics.append({
                        "code": "retrieval_target_input_canonicalized",
                        "severity": "warning",
                        "message": (
                            f"{event['path']}: removed retrieved collection placeholder(s) "
                            f"{event['removed']!r} from the input list; the collection remains "
                            "the retrieval goal's output and the raw model output is retained."
                        ),
                        "suggestion": (
                            "Review the source-data interpretation and ensure the goal description "
                            "preserves the requested business concept."
                        ),
                    })
                elif event.get("rule") == "arithmetic_expression_misplaced_in_effects":
                    diagnostics.append({
                        "code": "arithmetic_expression_removed_from_effects",
                        "severity": "warning",
                        "message": (
                            f"{event['path']}: removed arithmetic expression(s) {event['removed']!r} "
                            "from the effect list; effects describe boundary side effects, not calculations."
                        ),
                        "suggestion": (
                            "Review the goal description and formula assumptions. This repair does not "
                            "validate referenced fields, aggregation semantics, or numerical correctness."
                        ),
                    })
                elif event.get("rule") == "self_dependency_removed":
                    diagnostics.append({
                        "code": "invalid_self_dependency_canonicalized",
                        "severity": "warning",
                        "message": (
                            f"{event['path']}: removed self-dependency {event['removed']!r}; "
                            "the raw model output is retained."
                        ),
                        "suggestion": (
                            "Review the dependency graph. Dependencies must identify distinct "
                            "prerequisite goals; other unknown dependencies remain validation errors."
                        ),
                    })
                elif event.get("rule") == "objective_constraint_name_not_goal_dependency":
                    diagnostics.append({
                        "code": "objective_constraint_dependency_canonicalized",
                        "severity": "warning",
                        "message": (
                            f"{event['path']}: removed Objective Contract constraint name(s) "
                            f"{event['removed']!r} from the GoalSpec dependency graph; "
                            "the constraints remain preserved in the Objective Contract."
                        ),
                        "suggestion": (
                            "Review the namespace correction. GoalSpec deps may reference only "
                            "declared goal IDs; objective constraints are represented separately."
                        ),
                    })
            if structural_error:
                diagnostics.append({
                    "code": "goalspec_structural_nonconformance",
                    "severity": "error",
                    "message": str(structural_error),
                    "suggestion": "Regenerate using only the canonical GoalSpec schema and declared Θ vocabulary.",
                })
            has_errors = any(item.get("severity") == "error" for item in diagnostics)
            return structural_error is None and not has_errors, diagnostics, structural_error

        accepted, diagnostics, structural_error = assess(result)
        attempts = 1
        attempt_history = [{
            "attempt": 1, "json_valid": bool(result.get("json_valid")),
            "structural_valid": structural_error is None,
            "diagnostic_codes": [item.get("code") for item in diagnostics],
            "accepted_for_human_review": accepted,
            "latency_seconds": result.get("latency_seconds"),
        }]
        if not accepted:
            # Exactly one bounded refinement. The objective frame is retained along
            # with the immutable user objective and Core's concrete diagnostics.
            prior_text = str(result.get("text", ""))
            refinement_context = base_context + "\n\n" + build_refinement_context(
                request.prompt, prior_text, diagnostics
            )
            if agent_context is None:
                refined = runtime.decompose(
                    request.prompt, refinement_context, request.max_new_tokens
                )
            else:
                refined = runtime.decompose(
                    request.prompt, refinement_context, request.max_new_tokens,
                    agent_context=agent_context,
                )
            refined = prepare_agent_candidate(refined, request.prompt, objective_contract)
            attempts = 2
            accepted, refined_diagnostics, structural_error = assess(refined)
            attempt_history.append({
                "attempt": 2, "json_valid": bool(refined.get("json_valid")),
                "structural_valid": structural_error is None,
                "diagnostic_codes": [item.get("code") for item in refined_diagnostics],
                "accepted_for_human_review": accepted,
                "latency_seconds": refined.get("latency_seconds"),
            })
            result = refined
            diagnostics = refined_diagnostics

        core_analysis: dict[str, Any] = {
            "status": "not_analyzed", "model_profile": None, "goal_order": [],
            "goals": [], "gap_goal_ids": [], "shrink_candidates": [],
            "clarification": None, "discovery": "not_run_user_action_required",
            "hypergraph_composition": "deferred_to_discovery",
        }
        if structural_error is None and accepted and isinstance(result.get("goal_spec"), dict):
            # Run the actual GoalSpec gap-analysis algorithm against the active
            # model's calibrated profile. A mismatched/missing profile fails closed.
            active_model_id = str(result.get("model_id") or "")
            configured_profile = load_profile()
            profile_matches = bool(active_model_id and configured_profile.model_id == active_model_id)
            profile = configured_profile if profile_matches else ModelProfile(
                model_id=active_model_id or "uncalibrated-default", strict=True
            )
            core_spec = parse_studio_goal_spec(copy.deepcopy(result["goal_spec"]))
            gap = gap_analysis(core_spec, profile)
            ordered = core_spec.order() or []
            gap_requirements = classify_core_gap_requirements(
                ordered, [goal.id for goal in gap.gap]
            )
            core_analysis = {
                **gap_requirements,
                "status": "clarification_required" if gap.clarify else gap_requirements["status"],
                "model_profile": {
                    "model_id": profile.model_id, "calibrated_profile_matched": profile_matches,
                    "strict": profile.strict, "threshold": profile.tau,
                },
                "goal_order": [goal.id for goal in ordered],
                "goals": [{
                    "id": goal.id, "class": goal.cls, "rho": gap.rho.get(goal.id, 0.0),
                    "core_sigma": goal.sigma, "sigma_reason": goal.sigma_reason,
                    "exactness": goal.exactness, "n_estimate": goal.n,
                } for goal in ordered],
                "gap_goal_ids": [goal.id for goal in gap.gap],
                "shrink_candidates": [goal.id for goal in gap.shrink],
                "clarification": gap.clarify,
                "discovery": "not_run_user_action_required",
                "hypergraph_composition": "deferred_to_discovery",
            }

        # Return the full deterministic objective frame as inspectable provenance.
        result["agent_intelligence_context"] = agent_context_trace
        result["objective_contract"] = objective_contract
        result["objective_contract_v3"] = objective_contract_v3
        result["objective_intelligence_v3"] = {
            "schema": "taas.objective-intelligence/v1",
            "status": "clarification_required" if any(item.get("blocking") is True for item in objective_contract_v3.get("clarifications", [])) else "ready_for_human_review",
            "structurally_valid": not objective_contract_v3_errors,
            "validation_errors": objective_contract_v3_errors,
            "blocking_clarification_count": sum(1 for item in objective_contract_v3.get("clarifications", []) if item.get("blocking") is True),
            "semantic_correctness_verified": False,
            "discovery_authorized": False,
        }
        result["objective_coverage"] = build_outcome_coverage(
            request.prompt,
            result.get("goal_spec") if isinstance(result.get("goal_spec"), dict) else None,
        )
        result["objective_skill_traceability"] = build_objective_skill_traceability(
            objective=request.prompt,
            contract_v3=objective_contract_v3,
            coverage=result["objective_coverage"],
            agent_context_trace=agent_context_trace,
            goal_spec=result.get("goal_spec") if isinstance(result.get("goal_spec"), dict) else None,
        )
        result["core_analysis"] = core_analysis
        result["attempt_history"] = attempt_history
        result["structural_validation"] = {
            "valid": structural_error is None,
            "detail": structural_error,
            "theta_vocabulary_enforced": True,
        }
        result["conformance"] = {
            "accepted_for_human_review": accepted,
            "attempts": attempts,
            "max_attempts": 2,
            "unresolved_errors": [item for item in diagnostics if item.get("severity") == "error"],
            "semantic_correctness_verified": False,
            "auto_applied": False,
        }
        result["semantic_diagnostics"] = diagnostics
        result["semantic_review_required"] = True
        result["workflow"] = {
            "objective_interpretation": "completed",
            "goalspec_generation": "completed" if result.get("json_valid") else "failed",
            "structural_validation": "passed" if structural_error is None else "failed",
            "objective_conformance": "accepted_for_human_review" if accepted else "rejected",
            "core_gap_analysis": core_analysis.get("status", "not_analyzed"),
            "tool_discovery": ("awaiting_human_review_and_selected_tool_metadata" if accepted else "blocked_by_objective_conformance"),
            "hypergraph_composition": "deferred_to_tool_discovery",
            "tool_execution": "disabled",
            "semantic_correctness_verified": False,
        }
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/skills/validate", dependencies=[Depends(require_api_token)])
def skill_manifest_validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a reusable Skill manifest without persisting or activating it."""
    try:
        manifest = validate_skill_manifest(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    return {
        "valid": True, "manifest": manifest, "lifecycle_state": "draft",
        "semantic_correctness_verified": False, "tools_authorized": False,
        "execution_enabled": False,
    }


@app.post("/api/v1/skills", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_token)])
def skill_create(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a new immutable Skill version in draft state."""
    try:
        manifest = validate_skill_manifest(payload)
        resource = skill_registry.create_draft(
            manifest, actor=os.environ.get("TAAS_STUDIO_ACTOR", "studio-api")
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    except skill_registry.SkillRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Skill manifest must contain only strict JSON values") from exc
    return {
        **resource, "semantic_correctness_verified": False,
        "tools_authorized": False, "execution_enabled": False,
    }


@app.get("/api/v1/skills", dependencies=[Depends(require_api_token)])
def skill_list(skill_id: str | None = Query(default=None, max_length=63),
               limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return skill_registry.list_versions(skill_id=skill_id, limit=limit)


@app.get("/api/v1/skills/events", dependencies=[Depends(require_api_token)])
def skill_events(skill_id: str | None = Query(default=None, max_length=63),
                 limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    return skill_registry.list_events(skill_id=skill_id, limit=limit)


@app.get("/api/v1/skills/{skill_id}/versions/{version}", dependencies=[Depends(require_api_token)])
def skill_get(skill_id: str, version: str) -> dict[str, Any]:
    try:
        resource = skill_registry.get_version(skill_id, version)
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **resource, "semantic_correctness_verified": False,
        "tools_authorized": False, "execution_enabled": False,
    }


@app.get(
    "/api/v1/skills/{skill_id}/versions/{version}/dependency-graph",
    dependencies=[Depends(require_api_token)],
)
def skill_dependency_graph_get(skill_id: str, version: str) -> dict[str, Any]:
    """Return a read-only, exact-pin dependency DAG for a published Skill."""
    try:
        resource = skill_registry.get_version(skill_id, version)
        graph = skill_dependency_graph.resolve_skill_dependency_graph(
            skill_id, version, resource["manifest_sha256"], allow_revoked=True
        )
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except skill_dependency_graph.SkillDependencyNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except skill_dependency_graph.SkillDependencyGraphError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **graph,
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.get(
    "/api/v1/hypergraph/skills/{skill_id}/versions/{version}",
    dependencies=[Depends(require_api_token)],
)
def skill_hypergraph_projection_get(skill_id: str, version: str) -> dict[str, Any]:
    """Return a read-only Core Hypergraph projection of an exact published Skill DAG."""
    try:
        resource = skill_registry.get_version(skill_id, version)
        graph = skill_dependency_graph.resolve_skill_dependency_graph(
            skill_id, version, resource["manifest_sha256"], allow_revoked=True
        )
        projection = project_skill_dependency_graph(graph)
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except skill_dependency_graph.SkillDependencyNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except skill_dependency_graph.SkillDependencyGraphError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "skill_dependency_graph": graph,
        "hypergraph_projection": projection,
        "projection_source": "taas_core_skill_dependency_resolver",
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


class ObjectiveTraceabilityProjectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    traceability: dict[str, Any]


@app.post(
    "/api/v1/hypergraph/objective-traceability",
    dependencies=[Depends(require_api_token)],
)
def objective_traceability_hypergraph_projection(
    request: ObjectiveTraceabilityProjectionRequest,
) -> dict[str, Any]:
    """Project a prepare-response objective_skill_traceability record read-only."""
    try:
        projection = project_objective_skill_traceability(request.traceability)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "hypergraph_projection": projection,
        "projection_source": "prepare_response_objective_skill_traceability",
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.post("/api/v1/skills/{skill_id}/versions/{version}/validate", dependencies=[Depends(require_api_token)])
def skill_validate_saved_version(skill_id: str, version: str) -> dict[str, Any]:
    """Revalidate immutable stored bytes and advance draft -> validated."""
    try:
        resource = skill_registry.get_version(skill_id, version)
        manifest = validate_skill_manifest(resource["manifest"])
        if manifest != resource["manifest"]:
            raise HTTPException(status_code=409, detail="Stored Skill manifest is not canonical")
        resource = skill_registry.transition(
            skill_id, version, "validated",
            actor=os.environ.get("TAAS_STUDIO_ACTOR", "studio-api"),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except skill_registry.SkillRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **resource, "validation_scope": "structural_schema_and_field_invariants",
        "semantic_correctness_verified": False, "tools_authorized": False,
        "execution_enabled": False,
    }


@app.post("/api/v1/skills/{skill_id}/versions/{version}/publish", dependencies=[Depends(require_api_token)])
def skill_publish_version(skill_id: str, version: str) -> dict[str, Any]:
    """Publish a validated Skill as reusable guidance; this grants no capabilities."""
    try:
        resource = skill_registry.transition(
            skill_id, version, "published",
            actor=os.environ.get("TAAS_STUDIO_ACTOR", "studio-api"),
        )
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except skill_registry.SkillRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **resource, "published_as_guidance": True,
        "semantic_correctness_verified": False, "tools_authorized": False,
        "execution_enabled": False,
    }


class SkillSignatureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    publisher_id: str = Field(default="", max_length=128,
                              pattern=r"^$|^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
    statement: str = Field(default="", max_length=500)


def _skill_signature_binding(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_id": resource["skill_id"],
        "version": resource["version"],
        "manifest_sha256": resource["manifest_sha256"],
    }


@app.post("/api/v1/skills/{skill_id}/versions/{version}/sign",
          status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_token)])
def skill_sign_version(skill_id: str, version: str,
                       request: SkillSignatureRequest) -> dict[str, Any]:
    """Attest a registry signature for a published Skill version.

    The signature is a service-attested supply-chain record bound to the exact
    manifest digest. It proves registry issuance and integrity; it is not a
    portable third-party identity, authorization, or execution right.
    """
    try:
        resource = skill_registry.get_version(skill_id, version)
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if resource.get("lifecycle_state") != "published":
        raise HTTPException(
            status_code=409,
            detail="Only published Skill versions can be signed",
        )
    if resource.get("revoked"):
        raise HTTPException(
            status_code=409, detail="Revoked Skill versions cannot be signed",
        )
    actor = os.environ.get("TAAS_STUDIO_ACTOR", "studio-api")
    publisher = request.publisher_id or actor
    try:
        envelope = assurance_evidence.attest_evidence(
            evidence_type="publisher_signature",
            subject_binding=_skill_signature_binding(resource),
            issuer="taas-studio",
            assessor=actor,
            method="registry_manifest_signature",
            payload={"publisher_id": publisher, "statement": request.statement},
        )
        record = assurance_evidence.store_evidence(envelope)
    except assurance_evidence.EvidenceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except assurance_evidence.EvidenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "signature": {
            "evidence_id": record["evidence_id"],
            "evidence_type": record["evidence_type"],
            "subject_binding": record["subject_binding"],
            "publisher_id": publisher,
            "signed_by": record["assessor"],
            "observed_at": record["observed_at"],
            "expires_at": record["expires_at"],
        },
        "signature_scope": "registry_attested_not_portable_identity",
        "integrity_verified": True,
        "tools_authorized": False,
        "execution_enabled": False,
        "assessor_claim_truth_verified": False,
    }


@app.get("/api/v1/skills/{skill_id}/versions/{version}/signature",
         dependencies=[Depends(require_api_token)])
def skill_signature_status(skill_id: str, version: str) -> dict[str, Any]:
    """Return verified signature records bound to this exact Skill version."""
    try:
        resource = skill_registry.get_version(skill_id, version)
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        found = assurance_evidence.list_verified_evidence_for_subject(
            _skill_signature_binding(resource), expected_type="publisher_signature"
        )
    except assurance_evidence.EvidenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "skill_id": skill_id,
        "version": version,
        "manifest_sha256": resource["manifest_sha256"],
        "verified": found["count"] > 0,
        "signatures": [
            {
                "evidence_id": item["evidence_id"],
                "publisher_id": item["payload"].get("publisher_id"),
                "signed_by": item["assessor"],
                "observed_at": item["observed_at"],
                "expires_at": item["expires_at"],
            }
            for item in found["valid"]
        ],
        "invalid_records": found["invalid"],
        "signature_scope": "registry_attested_not_portable_identity",
        "tools_authorized": False,
        "execution_enabled": False,
    }


class SkillRevocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=500)


@app.post("/api/v1/skills/{skill_id}/versions/{version}/revoke",
          dependencies=[Depends(require_api_token)])
def skill_revoke_version(skill_id: str, version: str,
                         request: SkillRevocationRequest) -> dict[str, Any]:
    """Record an immutable revocation for a Skill version.

    Revoked versions refuse new dependency-graph resolution for binding and new
    signatures. The immutable version and its revocations remain inspectable;
    revocation is a provenance event, not a deletion or authorization change.
    """
    try:
        revocation = skill_registry.revoke_version(
            skill_id, version, reason=request.reason,
            actor=os.environ.get("TAAS_STUDIO_ACTOR", "studio-api"),
        )
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except skill_registry.SkillRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "revocation": revocation,
        "revoked": True,
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.get("/api/v1/skills/{skill_id}/versions/{version}/revocation",
         dependencies=[Depends(require_api_token)])
def skill_revocation_status(skill_id: str, version: str) -> dict[str, Any]:
    """Inspect the immutable revocation record for a Skill version, if any."""
    try:
        skill_registry.get_version(skill_id, version)
    except skill_registry.SkillRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    revocation = skill_registry.get_revocation(skill_id, version)
    return {
        "skill_id": skill_id,
        "version": version,
        "revoked": revocation is not None,
        "revocation": revocation,
        "tools_authorized": False,
        "execution_enabled": False,
    }


@app.post("/api/v1/agents/validate", dependencies=[Depends(require_api_token)])
def agent_manifest_validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a declarative Agent manifest without saving or executing it."""
    try:
        manifest = validate_agent_manifest(payload)
        _, resolved_skill_refs = resolve_agent_skill_bindings_or_http(manifest)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    return {
        "valid": True,
        "manifest": manifest,
        "resolved_skill_references": resolved_skill_refs,
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
        _, resolved_skill_refs = resolve_agent_skill_bindings_or_http(manifest)
        resource = agent_registry.create_draft(manifest)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    except agent_registry.AgentRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Agent manifest must contain only strict JSON values") from exc
    return {
        **resource,
        "resolved_skill_references": resolved_skill_refs,
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
        _, resolved_skill_refs = resolve_agent_skill_bindings_or_http(manifest)
        resource = agent_registry.transition(agent_id, version, "validated")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
    except agent_registry.AgentRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except agent_registry.AgentRegistryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **resource,
        "validation_scope": "structural_schema_cross_field_invariants_and_pinned_skill_resolution",
        "resolved_skill_references": resolved_skill_refs,
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
        validated_manifest = validate_agent_manifest(current["manifest"])
        _, resolved_skill_refs = resolve_agent_skill_bindings_or_http(validated_manifest)
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
        "resolved_skill_references": resolved_skill_refs,
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


class PolicyEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: dict[str, Any]
    facts: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/v1/policy/evaluate", dependencies=[Depends(require_api_token)])
def policy_evaluate(request: PolicyEvaluateRequest) -> dict[str, Any]:
    """Evaluate a governance verdict over a caller-asserted fact bundle.

    Facts supplied by the caller are labeled, never verified server-side; use the
    per-subject verdict endpoints for registry-assembled facts.
    """
    try:
        verdict = policy_engine.evaluate_policy(request.subject, request.facts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    verdict["facts_source"] = "caller_asserted"
    return verdict


def _gather_agent_skill_trust(manifest: dict[str, Any]) -> dict[str, Any]:
    """Assemble per-skill trust facts for the policy engine (fail closed)."""
    signature_required = os.environ.get("TAAS_POLICY_REQUIRE_SIGNATURES", "") == "1"
    try:
        _, external_refs = resolve_agent_skill_references(manifest)
    except AgentSkillBindingError as exc:
        return {"resolution_error": str(exc), "skills": [], "signature_required": signature_required}
    except Exception as exc:
        return {"resolution_error": f"binding_resolution_failed:{type(exc).__name__}",
                "skills": [], "signature_required": signature_required}
    skills = []
    for ref in external_refs:
        entry = {
            "skill_id": ref.get("id"),
            "version": ref.get("version"),
            "manifest_sha256": ref.get("manifest_sha256"),
            "resolution": "resolved",
            "revoked": False,
            "signature_required": signature_required,
            "signature_verified": None,
        }
        try:
            entry["revoked"] = skill_registry.is_revoked(ref["id"], ref["version"])
        except Exception:
            entry["revoked"] = None
        binding = {
            "skill_id": ref.get("id"),
            "version": ref.get("version"),
            "manifest_sha256": ref.get("manifest_sha256"),
        }
        try:
            found = assurance_evidence.list_verified_evidence_for_subject(
                binding, expected_type="publisher_signature"
            )
            entry["signature_verified"] = found["count"] > 0
        except assurance_evidence.EvidenceError:
            entry["signature_verified"] = None
        skills.append(entry)
    return {"skills": skills, "signature_required": signature_required}


@app.get("/api/v1/agents/{agent_id}/versions/{version}/policy-verdict",
         dependencies=[Depends(require_api_token)])
def agent_policy_verdict(agent_id: str, version: str) -> dict[str, Any]:
    """Server-assembled governance verdict for an exact Agent version.

    Diagnostic only: 'allow' means governance checks are satisfied — it never
    grants authorization or execution.
    """
    agent = _release_subject_or_http(agent_id, version)
    snapshot = None
    snapshot_id = agent.get("registry_snapshot_id")
    if snapshot_id:
        try:
            snapshot = agent_registry.get_mcp_snapshot(snapshot_id)
        except agent_registry.AgentRegistryError:
            snapshot = None
    readiness = release_readiness.evaluate_release_readiness(
        agent=agent, snapshot=snapshot,
        evidence_lookup=release_readiness.evidence_store_lookup(agent),
    )
    binding = release_readiness.build_release_subject_binding(agent)
    try:
        found = assurance_evidence.list_verified_evidence_for_subject(binding)
        evidence_summary = {
            "verified_records": found["count"],
            "invalid_records": len(found.get("invalid", [])),
        }
    except assurance_evidence.EvidenceError as exc:
        evidence_summary = {"verified_records": 0, "invalid_records": 0, "error": str(exc)}

    manifest = agent.get("manifest", {})
    facts = {
        "release_readiness": readiness,
        "evidence_summary": evidence_summary,
        "skill_trust": _gather_agent_skill_trust(manifest),
    }
    verdict = policy_engine.evaluate_policy(
        {
            "kind": "agent_version",
            "agent_id": agent_id,
            "version": version,
            "manifest_sha256": agent.get("manifest_sha256"),
            "registry_snapshot_id": snapshot_id,
        },
        facts,
    )
    verdict["facts_source"] = "registry_assembled"
    verdict["release_readiness"] = readiness
    return verdict


@app.get("/api/v1/agents/{agent_id}/versions/{version}/release-readiness", dependencies=[Depends(require_api_token)])
def agent_release_readiness(agent_id: str, version: str) -> dict[str, Any]:
    """Assess release readiness from immutable Agent and MCP snapshot evidence.

    This is a release diagnostic only: it never grants authorization, creates
    approvals, or enables execution.
    """
    try:
        agent = agent_registry.get_version(agent_id, version)
    except agent_registry.AgentRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    snapshot = None
    snapshot_id = agent.get("registry_snapshot_id")
    if snapshot_id:
        try:
            snapshot = agent_registry.get_mcp_snapshot(snapshot_id)
        except agent_registry.AgentRegistryError:
            snapshot = None

    return release_readiness.evaluate_release_readiness(
        agent=agent, snapshot=snapshot,
        evidence_lookup=release_readiness.evidence_store_lookup(agent),
    )


class AgentHumanApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    note: str = Field(default="", max_length=1000)
    ttl_seconds: int = Field(default=86400, ge=300, le=2592000)


def _release_subject_or_http(agent_id: str, version: str) -> dict[str, Any]:
    try:
        return agent_registry.get_version(agent_id, version)
    except agent_registry.AgentRegistryNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/agents/{agent_id}/versions/{version}/approvals", status_code=status.HTTP_201_CREATED,
          dependencies=[Depends(require_api_token)])
def agent_record_human_approval(agent_id: str, version: str,
                                request: AgentHumanApprovalRequest) -> dict[str, Any]:
    """Record an attested human approval bound to the exact Agent version.

    The approval is an immutable evidence record, never an authorization,
    tool grant, or execution right. It only satisfies the release-readiness
    human-approval check while fresh and while the bound digests are unchanged.
    """
    agent = _release_subject_or_http(agent_id, version)
    if agent.get("lifecycle_state") not in {"validated", "published"}:
        raise HTTPException(
            status_code=409,
            detail="Human approval requires a validated or published Agent version",
        )
    binding = release_readiness.build_release_subject_binding(agent)
    actor = os.environ.get("TAAS_STUDIO_ACTOR", "studio-api")
    try:
        envelope = assurance_evidence.attest_evidence(
            evidence_type="human_approval",
            subject_binding=binding,
            issuer="taas-studio",
            assessor=actor,
            method="studio_operator_approval",
            payload={"decision": "approved", "note": request.note},
            ttl_seconds=request.ttl_seconds,
        )
        record = assurance_evidence.store_evidence(envelope)
    except assurance_evidence.EvidenceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except assurance_evidence.EvidenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "approval": {
            "evidence_id": record["evidence_id"],
            "evidence_type": record["evidence_type"],
            "subject_binding": record["subject_binding"],
            "assessor": record["assessor"],
            "observed_at": record["observed_at"],
            "expires_at": record["expires_at"],
        },
        "integrity_verified": True,
        "authorization_granted": False,
        "execution_enabled": False,
        "assessor_claim_truth_verified": False,
    }


@app.get("/api/v1/agents/{agent_id}/versions/{version}/approvals", dependencies=[Depends(require_api_token)])
def agent_list_human_approvals(agent_id: str, version: str) -> dict[str, Any]:
    """List verified human approval records bound to this exact Agent version."""
    agent = _release_subject_or_http(agent_id, version)
    binding = release_readiness.build_release_subject_binding(agent)
    try:
        found = assurance_evidence.list_verified_evidence_for_subject(
            binding, expected_type="human_approval"
        )
    except assurance_evidence.EvidenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "agent_id": agent_id,
        "version": version,
        "subject_binding": binding,
        "count": found["count"],
        "approvals": [
            {
                "evidence_id": item["evidence_id"],
                "assessor": item["assessor"],
                "observed_at": item["observed_at"],
                "expires_at": item["expires_at"],
                "payload": item["payload"],
            }
            for item in found["valid"]
        ],
        "invalid_records": found["invalid"],
        "authorization_granted": False,
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
    return FileResponse(
        page,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
