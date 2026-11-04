"""PaMCP workbench launcher for the existing TaaS Studio process.

Import this router into the existing Studio app; it does not start workers or run experiments.
"""
from fastapi import APIRouter

from taas.studio.experiments_api import (
    experiment_catalog,
    experiment_detail,
    validate_run_draft,
    variants,
    workbench_status,
)

router = APIRouter(prefix="/api/v1/experiments", tags=["PaMCP Experiments"])
router.add_api_route("/catalog", experiment_catalog, methods=["GET"])
router.add_api_route("/catalog/{experiment_id}", experiment_detail, methods=["GET"])
router.add_api_route("/variants", variants, methods=["GET"])
router.add_api_route("/validate", validate_run_draft, methods=["POST"])
router.add_api_route("/workbench/status", workbench_status, methods=["GET"])
