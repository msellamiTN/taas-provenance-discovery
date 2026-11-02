"""Read-only Hugging Face model catalog adapter.

This module retrieves public model metadata only. It never downloads model files,
executes repository code, or loads weights.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

HF_MODELS_API = "https://huggingface.co/api/models"
_ALLOWED_SORTS = {"downloads", "likes", "lastModified"}


class ModelCatalogError(RuntimeError):
    """Raised when the upstream model catalog cannot provide a valid response."""


def _parameter_count(item: dict[str, Any]) -> int | None:
    safe = item.get("safetensors")
    if not isinstance(safe, dict):
        return None
    parameters = safe.get("parameters")
    if not isinstance(parameters, dict):
        return None
    counts = [value for value in parameters.values() if isinstance(value, int) and value >= 0]
    return sum(counts) if counts else None


def normalize_model(item: dict[str, Any]) -> dict[str, Any]:
    """Expose a bounded, non-executable subset of Hugging Face model metadata."""
    model_id = item.get("id") or item.get("modelId")
    if not isinstance(model_id, str) or not model_id or len(model_id) > 256:
        raise ValueError("Hugging Face returned a model without a valid repository ID")
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    tags = [tag for tag in tags if isinstance(tag, str)]
    pipeline = item.get("pipeline_tag")
    library = item.get("library_name")
    safetensors = item.get("safetensors")
    return {
        "model_id": model_id,
        "url": f"https://huggingface.co/{model_id}",
        "pipeline_tag": pipeline if isinstance(pipeline, str) else None,
        "library_name": library if isinstance(library, str) else None,
        "downloads": item.get("downloads") if isinstance(item.get("downloads"), int) else None,
        "likes": item.get("likes") if isinstance(item.get("likes"), int) else None,
        "last_modified": item.get("lastModified") if isinstance(item.get("lastModified"), str) else None,
        "gated": item.get("gated") if isinstance(item.get("gated"), (bool, str)) else None,
        "private": item.get("private") if isinstance(item.get("private"), bool) else None,
        "license": next((tag.removeprefix("license:") for tag in tags if tag.startswith("license:")), None),
        "tags": tags[:40],
        "safetensors": isinstance(safetensors, dict),
        "parameter_count": _parameter_count(item),
    }


def search_models(
    query: str,
    limit: int = 10,
    sort: str = "downloads",
    pipeline_tag: str | None = None,
) -> list[dict[str, Any]]:
    """Search Hugging Face model metadata with bounded input and network timeouts."""
    query = query.strip()
    if not query or len(query) > 120:
        raise ValueError("query must contain 1 to 120 characters")
    if not 1 <= limit <= 30:
        raise ValueError("limit must be between 1 and 30")
    if sort not in _ALLOWED_SORTS:
        raise ValueError(f"sort must be one of {sorted(_ALLOWED_SORTS)}")
    if pipeline_tag is not None and (not pipeline_tag.strip() or len(pipeline_tag) > 80):
        raise ValueError("pipeline_tag must contain 1 to 80 characters")

    headers = {"User-Agent": "TaaS-Studio/0.1"}
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params: dict[str, Any] = {"search": query, "limit": limit, "sort": sort, "direction": -1}
    if pipeline_tag:
        params["pipeline_tag"] = pipeline_tag.strip()

    try:
        response = httpx.get(HF_MODELS_API, params=params, headers=headers, timeout=12.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelCatalogError(f"Hugging Face model catalog request failed: {type(exc).__name__}") from exc
    if not isinstance(payload, list):
        raise ModelCatalogError("Hugging Face returned an unexpected model catalog response")
    results = []
    for item in payload[:limit]:
        if isinstance(item, dict):
            try:
                results.append(normalize_model(item))
            except ValueError:
                continue
    return results
