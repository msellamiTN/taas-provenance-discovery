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



def get_model_details(model_id: str) -> dict[str, Any]:
    """Fetch a bounded, non-executable model detail record from the HF API.

    Only a strict repository-ID form is accepted. The function returns a
    whitelist of configuration metadata and never fetches repository files.
    """
    import re

    from urllib.parse import quote

    model_id = model_id.strip()
    if len(model_id) > 256 or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*",
        model_id,
    ):
        raise ValueError("model_id must be a Hugging Face namespace/repository identifier")

    headers = {"User-Agent": "TaaS-Studio/0.1"}
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.get(
            f"{HF_MODELS_API}/{quote(model_id, safe='/')}",
            params={"blobs": "false"},
            headers=headers,
            timeout=12.0,
        )
        response.raise_for_status()
        item = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelCatalogError(
            f"Hugging Face model detail request failed: {type(exc).__name__}"
        ) from exc

    if not isinstance(item, dict):
        raise ModelCatalogError("Hugging Face returned an unexpected model detail response")

    normalized = normalize_model(item)
    raw_config = item.get("config")
    raw_config = raw_config if isinstance(raw_config, dict) else {}
    nested = raw_config.get("text_config")
    if isinstance(nested, dict):
        # Preserve both the top-level and text config values, preferring explicit
        # text_config values for decoder dimensions in multimodal repositories.
        config = {**raw_config, **nested}
    else:
        config = raw_config

    architecture_fields = (
        "model_type",
        "architectures",
        "num_hidden_layers",
        "num_attention_heads",
        "num_key_value_heads",
        "hidden_size",
        "head_dim",
        "max_position_embeddings",
        "max_sequence_length",
        "vocab_size",
        "torch_dtype",
    )
    architecture = {
        key: config[key]
        for key in architecture_fields
        if key in config and isinstance(config[key], (str, int, float, list))
    }
    # Do not infer attention dimensions or context limits from model names.
    kv_complete = all(
        isinstance(architecture.get(key), int) and architecture[key] > 0
        for key in ("num_hidden_layers", "num_key_value_heads", "head_dim")
    )
    context = architecture.get("max_position_embeddings") or architecture.get("max_sequence_length")
    architecture["kv_cache_dimensions_complete"] = kv_complete
    architecture["context_limit_reported"] = isinstance(context, int) and context > 0

    return {
        **normalized,
        "architecture": architecture,
        "architecture_source": "Hugging Face model API config",
        "architecture_complete_for_kv_estimate": kv_complete,
        "weights_downloaded": False,
        "model_code_executed": False,
    }



def inspect_model_artifacts(model_id: str) -> dict[str, Any]:
    """Inspect HF repository file metadata without downloading any artifact.

    File sizes are reported only when the Hub API supplies them. Backend labels
    are candidates based on file extensions, not proof of runtime compatibility.
    """
    import re
    from urllib.parse import quote

    model_id = model_id.strip()
    if len(model_id) > 256 or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*",
        model_id,
    ):
        raise ValueError("model_id must be a Hugging Face namespace/repository identifier")

    headers = {"User-Agent": "TaaS-Studio/0.1"}
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.get(
            f"{HF_MODELS_API}/{quote(model_id, safe='/')}",
            params={"blobs": "true"},
            headers=headers,
            timeout=12.0,
        )
        response.raise_for_status()
        item = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelCatalogError(
            f"Hugging Face artifact metadata request failed: {type(exc).__name__}"
        ) from exc

    if not isinstance(item, dict):
        raise ModelCatalogError("Hugging Face returned an unexpected artifact metadata response")

    siblings = item.get("siblings")
    if not isinstance(siblings, list):
        siblings = []

    files: list[dict[str, Any]] = []
    total_known_bytes = 0
    size_complete = True
    formats: set[str] = set()
    quantization_hints: set[str] = set()
    for sibling in siblings[:1000]:
        if not isinstance(sibling, dict):
            continue
        name = sibling.get("rfilename")
        if not isinstance(name, str) or not name or len(name) > 512:
            continue
        lower = name.lower()
        if lower.endswith(".safetensors"):
            fmt = "safetensors"
        elif lower.endswith((".gguf", ".ggml")):
            fmt = "gguf" if lower.endswith(".gguf") else "ggml"
        elif lower.endswith((".bin", ".pt", ".pth")):
            fmt = "pytorch"
        elif lower.endswith(".onnx"):
            fmt = "onnx"
        elif lower.endswith((".h5", ".hdf5")):
            fmt = "hdf5"
        elif lower.endswith((".json", ".model", ".txt", ".md", ".py")):
            fmt = "metadata_or_code"
        else:
            fmt = "other"
        if fmt in {"safetensors", "gguf", "ggml", "pytorch", "onnx", "hdf5"}:
            formats.add(fmt)

        size = sibling.get("size")
        lfs = sibling.get("lfs")
        if not isinstance(size, int) or size < 0:
            size = lfs.get("size") if isinstance(lfs, dict) else None
        if isinstance(size, int) and size >= 0:
            total_known_bytes += size
        else:
            size_complete = False

        for hint in ("awq", "gptq", "exl2", "bnb", "bitsandbytes", "int4", "int8", "fp8"):
            if hint in lower:
                quantization_hints.add(hint)
        files.append({
            "name": name,
            "format": fmt,
            "size_bytes": size if isinstance(size, int) and size >= 0 else None,
            "sha256": (
                lfs.get("oid")
                if isinstance(lfs, dict)
                and isinstance(lfs.get("oid"), str)
                and re.fullmatch(r"[0-9a-fA-F]{64}", lfs["oid"])
                else None
            ),
        })

    backend_candidates = []
    if "gguf" in formats:
        backend_candidates.append({
            "backend": "llama.cpp",
            "evidence": "Repository contains GGUF file(s)",
            "compatibility": "candidate_only",
        })
    if formats.intersection({"safetensors", "pytorch"}):
        backend_candidates.append({
            "backend": "Transformers",
            "evidence": "Repository contains Safetensors or PyTorch weight file(s)",
            "compatibility": "candidate_only",
        })
    if "onnx" in formats:
        backend_candidates.append({
            "backend": "ONNX Runtime",
            "evidence": "Repository contains ONNX file(s)",
            "compatibility": "candidate_only",
        })

    return {
        "model_id": model_id,
        "file_count": len(files),
        "files": files[:200],
        "files_truncated": len(files) > 200,
        "formats": sorted(formats),
        "quantization_filename_hints": sorted(quantization_hints),
        "known_artifact_bytes": total_known_bytes,
        "artifact_size_complete": size_complete and len(siblings) <= 1000,
        "backend_candidates": backend_candidates,
        "t4_assessment": {
            "gpu": "Tesla T4",
            "compute_capability": "7.5",
            "status": "not_verified",
            "reason": (
                "Repository metadata alone cannot establish T4 compatibility. "
                "Backend version, kernels, quantization implementation, model architecture "
                "and runtime memory must be validated by an actual load and inference test."
            ),
        },
        "weights_downloaded": False,
        "model_code_executed": False,
        "metadata_source": "Hugging Face model API siblings (blobs=true)",
    }
