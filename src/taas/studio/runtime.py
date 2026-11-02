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
