"""Mountable baseline catalogue and preview router."""
from fastapi import APIRouter, Depends

from taas.studio.experiments_api import (
    baseline_catalog,
    baseline_detail,
    baseline_preview,
    require_token,
)

router = APIRouter(
    prefix="/api/v1/baselines",
    tags=["PaMCP Baselines"],
    dependencies=[Depends(require_token)],
)
router.add_api_route("/catalog", baseline_catalog, methods=["GET"])
router.add_api_route("/catalog/{baseline_id}", baseline_detail, methods=["GET"])
router.add_api_route("/preview", baseline_preview, methods=["POST"])
