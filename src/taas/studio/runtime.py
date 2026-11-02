"""Best-effort hardware diagnostics for the interactive Studio runtime."""
from __future__ import annotations

import importlib.util
import subprocess
from typing import Any


def probe_hardware() -> dict[str, Any]:
    """Report observed GPU/CUDA state without loading or executing a model."""
    result: dict[str, Any] = {
        "gpu_detected": False,
        "gpu": None,
        "nvidia_smi_available": False,
        "torch_installed": importlib.util.find_spec("torch") is not None,
        "cuda_available": False,
        "inference_ready": False,
        "notes": [],
    }
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,driver_version,compute_cap",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        proc = None
        result["notes"].append("nvidia-smi is unavailable; no NVIDIA GPU could be verified.")

    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        fields = [part.strip() for part in proc.stdout.strip().splitlines()[0].split(",")]
        if len(fields) >= 5:
            try:
                result["gpu"] = {
                    "name": fields[0],
                    "memory_total_mib": int(float(fields[1])),
                    "memory_free_mib": int(float(fields[2])),
                    "driver_version": fields[3],
                    "compute_capability": fields[4],
                }
                result["gpu_detected"] = True
                result["nvidia_smi_available"] = True
            except ValueError:
                result["notes"].append("GPU was reported, but nvidia-smi output could not be parsed.")
        else:
            result["notes"].append("nvidia-smi returned an unexpected GPU information format.")
    elif proc is not None:
        result["notes"].append("nvidia-smi did not report an available NVIDIA GPU.")

    if result["torch_installed"]:
        try:
            import torch

            result["cuda_available"] = bool(torch.cuda.is_available())
            if result["cuda_available"]:
                device = torch.cuda.get_device_properties(0)
                result["torch_device"] = {
                    "name": device.name,
                    "total_memory_mib": int(device.total_memory // (1024 * 1024)),
                    "compute_capability": f"{device.major}.{device.minor}",
                }
                result["inference_ready"] = True
            else:
                result["notes"].append("PyTorch is installed, but torch.cuda.is_available() is false.")
        except Exception as exc:
            result["notes"].append(f"PyTorch CUDA probe failed: {type(exc).__name__}.")
    else:
        result["notes"].append("PyTorch is not installed; CUDA inference has not been configured.")

    if result["gpu_detected"] and not result["cuda_available"]:
        result["notes"].append("A GPU is visible to the host, but a CUDA inference backend is not yet verified.")
    return result


# Approximate storage cost per parameter. These are weight-storage estimates,
# not claims about runtime compatibility or total inference memory.
_QUANTIZATION_BYTES = {
    "fp16": 2.0,
    "int8": 1.0,
    "int4": 0.5,
}


def estimate_model_memory(
    parameters_billion: float,
    quantization: str = "int4",
    overhead_fraction: float = 0.20,
    runtime_reserve_gib: float = 2.0,
    num_hidden_layers: int | None = None,
    num_key_value_heads: int | None = None,
    head_dim: int | None = None,
    context_length: int | None = None,
    batch_size: int = 1,
    kv_cache_dtype: str = "fp16",
) -> dict[str, Any]:
    """Estimate weights and, when architecture inputs exist, decoder KV cache.

    The KV formula is 2 * layers * KV heads * head dimension * context tokens
    * batch * bytes per element. Activations, CUDA workspaces, fragmentation and
    backend-specific quantization metadata remain excluded. This is not a load
    guarantee.
    ""
    import math

    if not math.isfinite(parameters_billion) or parameters_billion <= 0 or parameters_billion > 200:
        raise ValueError("parameters_billion must be finite and in (0, 200]")
    if quantization not in _QUANTIZATION_BYTES:
        raise ValueError(f"quantization must be one of {sorted(_QUANTIZATION_BYTES)}")
    if not math.isfinite(overhead_fraction) or not 0 <= overhead_fraction <= 1:
        raise ValueError("overhead_fraction must be finite and between 0 and 1")
    if not math.isfinite(runtime_reserve_gib) or runtime_reserve_gib < 0 or runtime_reserve_gib > 64:
        raise ValueError("runtime_reserve_gib must be finite and between 0 and 64")
    kv_inputs = (num_hidden_layers, num_key_value_heads, head_dim, context_length)
    if any(value is not None for value in kv_inputs):
        if any(not isinstance(value, int) or value <= 0 for value in kv_inputs):
            raise ValueError("all KV-cache dimensions must be positive integers when any is provided")
        if batch_size < 1 or batch_size > 128:
            raise ValueError("batch_size must be between 1 and 128")
        if kv_cache_dtype not in _KV_CACHE_BYTES:
            raise ValueError(f"kv_cache_dtype must be one of {sorted(_KV_CACHE_BYTES)}")
        if context_length > 1_000_000:
            raise ValueError("context_length must not exceed 1000000")
        kv_cache_gib = (
            2 * num_hidden_layers * num_key_value_heads * head_dim
            * context_length * batch_size * _KV_CACHE_BYTES[kv_cache_dtype]
            / (1024 ** 3)
        )
    else:
        kv_cache_gib = None

    # Decimal parameter count, binary GiB conversion.
    weight_gib = parameters_billion * 1_000_000_000 * _QUANTIZATION_BYTES[quantization] / (1024 ** 3)
    estimated_gib = weight_gib * (1 + overhead_fraction) + (kv_cache_gib or 0.0) + runtime_reserve_gib
    hardware = probe_hardware()
    free_gib = None
    fits_observed_free_memory = None
    if hardware.get("gpu") and hardware["gpu"].get("memory_free_mib") is not None:
        free_gib = hardware["gpu"]["memory_free_mib"] / 1024
        fits_observed_free_memory = estimated_gib <= free_gib

    return {
        "parameters_billion": parameters_billion,
        "quantization": quantization,
        "weight_memory_gib": round(weight_gib, 3),
        "overhead_fraction": overhead_fraction,
        "runtime_reserve_gib": runtime_reserve_gib,
        "kv_cache_memory_gib": round(kv_cache_gib, 3) if kv_cache_gib is not None else None,
        "kv_cache_assumptions": {
            "num_hidden_layers": num_hidden_layers,
            "num_key_value_heads": num_key_value_heads,
            "head_dim": head_dim,
            "context_length": context_length,
            "batch_size": batch_size,
            "dtype": kv_cache_dtype if kv_cache_gib is not None else None,
        },
        "estimated_memory_gib": round(estimated_gib, 3),
        "observed_free_gpu_memory_gib": round(free_gib, 3) if free_gib is not None else None,
        "fits_observed_free_memory": fits_observed_free_memory,
        "estimate_scope": "weights + configurable overhead + optional decoder KV cache + runtime reserve; excludes activations and backend workspaces",
        "load_guaranteed": False,
    }
