"""Authenticated read-only assurance evidence routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from taas.studio.assurance_evidence import EvidenceError, inspect_verified_evidence


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

    return router
