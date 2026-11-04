"""Mountable PaMCP experiment catalogue and configuration router."""
from fastapi import APIRouter

from taas.studio.api import require_api_token
from taas.studio.experiments_api import (
    experiment_catalog,
    experiment_detail,
    experiment_baselines,
    validate_run_draft,
    variants,
    workbench_status,
)

router = APIRouter(
    prefix="/api/v1/experiments",
    tags=["PaMCP Experiments"],
    dependencies=[require_api_token],
)
router.add_api_route("/catalog", experiment_catalog, methods=["GET"])
router.add_api_route("/catalog/{experiment_id}", experiment_detail, methods=["GET"])
router.add_api_route("/catalog/{experiment_id}/baselines", experiment_baselines, methods=["GET"])
router.add_api_route("/variants", variants, methods=["GET"])
router.add_api_route("/validate", validate_run_draft, methods=["POST"])
router.add_api_route("/workbench/status", workbench_status, methods=["GET"])
