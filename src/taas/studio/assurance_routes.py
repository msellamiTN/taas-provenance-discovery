"""Authenticated read-only assurance evidence routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from taas.studio.assurance_evidence import (
    EvidenceError, inspect_verified_evidence, list_verified_evidence_for_subject,
)


class EvidenceFreshnessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bindings: list[dict[str, Any]] = Field(min_length=1, max_length=50)
    evidence_type: str | None = Field(default=None, max_length=128)


def build_assurance_router(require_api_token):
    router = APIRouter()

    @router.get("/api/v1/assurance/evidence/{evidence_id}", dependencies=[Depends(require_api_token)])
    def inspect_evidence(evidence_id: str) -> dict[str, Any]:
        try:
            record = inspect_verified_evidence(evidence_id)
        except EvidenceError as exc:
            code = 404 if "not found" in str(exc).lower() else 422
            raise HTTPException(status_code=code, detail=str(exc)) from exc
        return {
            "evidence": record,
            "integrity_verified": True,
            "freshness": "fresh",
            "assessor_claim_truth_verified": False,
            "authorization_granted": False,
            "execution_performed": False,
        }

    @router.post("/api/v1/assurance/evidence/freshness", dependencies=[Depends(require_api_token)])
    def evidence_freshness_batch(request: EvidenceFreshnessRequest) -> dict[str, Any]:
        """Verify freshness+integrity for a batch of subject bindings.

        Each binding is re-verified independently and fail-closed: a binding
        that errors reports ``unverifiable`` — never silently counts as
        satisfied evidence. This reports record state, not assessor truth.
        """
        results = []
        for binding in request.bindings:
            try:
                found = list_verified_evidence_for_subject(
                    binding, expected_type=request.evidence_type)
                results.append({
                    "subject_binding": binding,
                    "status": "verified" if found["count"] else "no_fresh_records",
                    "verified_records": found["count"],
                    "invalid_records": len(found.get("invalid", [])),
                    "evidence_ids": [item["evidence_id"] for item in found["valid"]],
                })
            except EvidenceError as exc:
                results.append({
                    "subject_binding": binding,
                    "status": "unverifiable",
                    "verified_records": 0,
                    "invalid_records": 0,
                    "error": str(exc),
                })
        return {
            "schema": "taas.evidence-freshness/v1",
            "count": len(results),
            "results": results,
            "assessor_claim_truth_verified": False,
            "authorization_granted": False,
            "execution_performed": False,
        }

    return router
