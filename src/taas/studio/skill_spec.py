"""Strict declarative contract for reusable, versioned TaaS Skills."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ID = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SkillMetadata(StrictModel):
    id: str = Field(min_length=3, max_length=63)
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=_SEMVER.pattern)
    description: str = Field(default="", max_length=1000)

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not _ID.fullmatch(value):
            raise ValueError("id must be a lowercase DNS-style identifier (3-63 chars)")
        return value


class SkillDependencyReference(StrictModel):
    """Exact immutable reference to another published Skill version."""

    id: str = Field(min_length=3, max_length=63, pattern=_ID.pattern)
    version: str = Field(pattern=_SEMVER.pattern)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SkillSpec(StrictModel):
    instructions: str = Field(min_length=1, max_length=8000)
    trigger_phrases: list[str] = Field(min_length=1, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)
    dependencies: list[SkillDependencyReference] = Field(default_factory=list, max_length=32)

    @field_validator("trigger_phrases")
    @classmethod
    def validate_triggers(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 160 for value in normalized):
            raise ValueError("trigger phrases must contain 1-160 non-empty characters")
        folded = [value.casefold() for value in normalized]
        if len(folded) != len(set(folded)):
            raise ValueError("trigger phrases must be unique (case-insensitive)")
        return normalized

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        if any(not value or len(value) > 48 for value in normalized):
            raise ValueError("tags must contain 1-48 non-empty characters")
        if len(normalized) != len(set(normalized)):
            raise ValueError("tags must be unique")
        return normalized

    @field_validator("dependencies")
    @classmethod
    def validate_dependencies(
        cls, values: list[SkillDependencyReference]
    ) -> list[SkillDependencyReference]:
        ids = [value.id for value in values]
        if len(ids) != len(set(ids)):
            raise ValueError("dependencies must not reference the same Skill ID more than once")
        return values


class SkillManifest(StrictModel):
    apiVersion: Literal["taas.ai/v1alpha1"] = "taas.ai/v1alpha1"
    kind: Literal["Skill"] = "Skill"
    metadata: SkillMetadata
    spec: SkillSpec

    @model_validator(mode="after")
    def reject_self_dependency(self):
        if any(item.id == self.metadata.id for item in self.spec.dependencies):
            raise ValueError("a Skill cannot depend on itself")
        return self


def validate_skill_manifest(payload: dict) -> dict:
    """Return normalized JSON-compatible Skill manifest or raise ValidationError.

    Preserve the canonical shape of legacy manifests that predate dependencies:
    the new optional field is omitted unless the author explicitly supplied it.
    """
    normalized = SkillManifest.model_validate(payload).model_dump(mode="json")
    if "dependencies" not in payload.get("spec", {}):
        normalized["spec"].pop("dependencies", None)
    return normalized
