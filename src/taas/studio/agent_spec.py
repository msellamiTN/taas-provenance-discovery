"""Declarative Agent resource contract for TaaS Studio.

This module validates agent configuration only. It does not authorize tools,
load models, persist resources, or execute an agent.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_AGENT_ID = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
_TOOL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgentMetadata(StrictModel):
    id: str = Field(min_length=3, max_length=63)
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=_SEMVER.pattern)
    description: str = Field(default="", max_length=1000)

    @field_validator("id")
    @classmethod
    def valid_agent_id(cls, value: str) -> str:
        if not _AGENT_ID.fullmatch(value):
            raise ValueError("id must be a lowercase DNS-style identifier (3-63 chars)")
        return value


class AgentModelBinding(StrictModel):
    provider: Literal["huggingface"] = "huggingface"
    model_id: str = Field(min_length=3, max_length=257)
    revision: str | None = Field(default=None, min_length=40, max_length=40)

    @field_validator("revision")
    @classmethod
    def valid_revision(cls, value: str | None) -> str | None:
        if value is not None and not _REVISION.fullmatch(value):
            raise ValueError("revision must be a full 40-character immutable Hub commit SHA")
        return value

    @field_validator("model_id")
    @classmethod
    def valid_model_id(cls, value: str) -> str:
        if not _MODEL_ID.fullmatch(value):
            raise ValueError("model_id must be a Hugging Face namespace/repository identifier")
        return value


class AgentToolGrant(StrictModel):
    server_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)

    @field_validator("server_id")
    @classmethod
    def valid_server_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
            raise ValueError("server_id contains unsupported characters")
        return value

    @field_validator("tool_name")
    @classmethod
    def valid_tool_name(cls, value: str) -> str:
        if not _TOOL_NAME.fullmatch(value):
            raise ValueError("tool_name contains unsupported characters")
        return value


class AgentSkill(StrictModel):
    """A versioned, objective-triggered skill bundled into an immutable Agent version."""

    id: str = Field(min_length=3, max_length=63, pattern=r"^[a-z][a-z0-9-]{2,62}$")
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=_SEMVER.pattern)
    description: str = Field(default="", max_length=1000)
    instructions: str = Field(min_length=1, max_length=8000)
    trigger_phrases: list[str] = Field(min_length=1, max_length=20)

    @field_validator("trigger_phrases")
    @classmethod
    def validate_trigger_phrases(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 160 for value in normalized):
            raise ValueError("skill trigger phrases must contain 1-160 non-empty characters")
        folded = [value.casefold() for value in normalized]
        if len(folded) != len(set(folded)):
            raise ValueError("skill trigger phrases must be unique (case-insensitive)")
        return normalized


class AgentResources(StrictModel):
    max_new_tokens: int = Field(default=1024, ge=1, le=2048)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    max_tool_calls: int = Field(default=0, ge=0, le=100)


class AgentApprovalPolicy(StrictModel):
    require_human_approval: bool = True
    require_assurance: bool = True
    allow_side_effects: bool = False


class AgentSpec(StrictModel):
    model: AgentModelBinding
    instructions: str = Field(min_length=1, max_length=12000)
    skills: list[AgentSkill] = Field(default_factory=list, max_length=32)
    goal_spec_template: dict | None = None
    tool_allowlist: list[AgentToolGrant] = Field(default_factory=list, max_length=100)
    resources: AgentResources = Field(default_factory=AgentResources)
    approval: AgentApprovalPolicy = Field(default_factory=AgentApprovalPolicy)

    @model_validator(mode="after")
    def unique_tool_grants(self):
        skill_ids = [item.id for item in self.skills]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("skills contains duplicate skill IDs")
        grants = [(item.server_id, item.tool_name) for item in self.tool_allowlist]
        if len(grants) != len(set(grants)):
            raise ValueError("tool_allowlist contains duplicate server_id/tool_name grants")
        if self.resources.max_tool_calls == 0 and self.tool_allowlist:
            raise ValueError("max_tool_calls must be greater than zero when tool_allowlist is non-empty")
        if self.resources.max_tool_calls > 0 and not self.tool_allowlist:
            raise ValueError("tool_allowlist must be non-empty when max_tool_calls is greater than zero")
        if self.approval.allow_side_effects and not self.approval.require_human_approval:
            raise ValueError("side-effecting agents must require human approval")
        return self


class AgentManifest(StrictModel):
    apiVersion: Literal["taas.ai/v1alpha1"] = "taas.ai/v1alpha1"
    kind: Literal["Agent"] = "Agent"
    metadata: AgentMetadata
    spec: AgentSpec


def validate_agent_manifest(payload: dict) -> dict:
    """Return a normalized JSON-compatible manifest or raise Pydantic ValidationError."""
    manifest = AgentManifest.model_validate(payload)
    normalized = manifest.model_dump(mode="json")
    # Preserve the canonical byte shape of pre-skills manifests. This keeps
    # immutable versions created by earlier Studio builds verifiable.
    if "skills" not in payload.get("spec", {}):
        normalized["spec"].pop("skills", None)
    return normalized
