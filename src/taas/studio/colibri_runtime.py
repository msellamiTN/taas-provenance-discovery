"""Colibri adapter — OpenAI-compatible hierarchical MoE inference server.

Colibri (github.com/JustVugg/colibri) runs large MoE models on constrained
hardware: hot experts on GPU, warm in RAM, cold streamed from NVMe — which is
what makes a T4/limited-VRAM Colab runtime viable. It exposes an
OpenAI-compatible ``/v1`` endpoint; this adapter maps the Studio
model-runtime interface onto it. Select with ``provider: "colibri"``;
configure with ``TAAS_COLIBRI_BASE_URL`` (default ``http://127.0.0.1:8090/v1``).
"""
from __future__ import annotations

import json
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from typing import Any

from taas.studio.model_runtime import (
    ModelRuntimeError, diagnose_goal_spec, parse_goal_spec_response,
)
from taas.studio.analyst_contract import build_analyst_system_prompt


class ColibriModelRuntime:
    """Calls a colibri OpenAI-compatible server; never shells out."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model_name: str | None = None
        self._last_inference_at: float | None = None
        self._last_error: str | None = None

    @staticmethod
    def _base_url() -> str:
        value = os.environ.get("TAAS_COLIBRI_BASE_URL", "http://127.0.0.1:8090/v1").rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ModelRuntimeError("TAAS_COLIBRI_BASE_URL must be an http(s) URL without embedded credentials")
        return value

    def _request(self, path: str, payload: dict[str, Any] | None = None,
                 timeout: int = 30) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self._base_url() + path, data=data,
                          headers={"Content-Type": "application/json"} if data else {})
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ModelRuntimeError(f"Colibri HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ModelRuntimeError(
                f"Cannot reach Colibri at {self._base_url()}. "
                f"Start the colibri server (start-here.sh) and verify TAAS_COLIBRI_BASE_URL. {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelRuntimeError(f"Colibri returned invalid JSON: {exc}") from exc
        if not isinstance(result, dict):
            raise ModelRuntimeError("Colibri returned an unexpected response shape")
        return result

    def status(self) -> dict[str, Any]:
        try:
            payload = self._request("/models", timeout=4)
            models = [{"name": m.get("id")}
                      for m in payload.get("data", []) if isinstance(m, dict)]
            return {
                "provider": "colibri", "available": True,
                "base_url": self._base_url(),
                "model_selected": self._model_name, "models": models,
                "last_inference_at": self._last_inference_at,
                "last_error": self._last_error,
                "execution_performed": False,
                "placement": "hot-experts-gpu / warm-ram / cold-nvme",
            }
        except ModelRuntimeError as exc:
            return {"provider": "colibri", "available": False, "base_url": None,
                    "model_selected": self._model_name, "models": [],
                    "last_inference_at": self._last_inference_at,
                    "last_error": str(exc), "execution_performed": False}

    def load(self, model_id: str, device: str = "auto") -> dict[str, Any]:
        name = model_id.strip()
        if not name or len(name) > 256 or any(ch.isspace() for ch in name):
            raise ValueError("Colibri model name must be a non-empty id without whitespace")
        available = {m["name"] for m in self.status().get("models", [])}
        if available and name not in available:
            raise ModelRuntimeError(
                f"model {name!r} not served by colibri (serving: {sorted(available)})")
        with self._lock:
            self._model_name = name
            self._last_error = None
        result = self.status()
        result["model_selected"] = name
        result["load_semantics"] = "validated; colibri manages expert placement"
        return result

    def _generate(self, messages: list[dict[str, str]], max_new_tokens: int,
                  temperature: float) -> dict[str, Any]:
        if not 1 <= max_new_tokens <= 4096:
            raise ValueError("max_new_tokens must be between 1 and 4096")
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if not self._model_name:
            raise ModelRuntimeError("Select a colibri model before inference")
        started = time.perf_counter()
        result = self._request("/chat/completions", {
            "model": self._model_name, "messages": messages,
            "max_tokens": max_new_tokens, "temperature": temperature,
            "stream": False}, timeout=600)
        elapsed = time.perf_counter() - started
        choices = result.get("choices") or []
        content = (choices[0].get("message", {}) or {}).get("content", "") if choices else ""
        if not isinstance(content, str):
            raise ModelRuntimeError("Colibri response lacked choices[0].message.content")
        usage = result.get("usage") or {}
        self._last_inference_at = time.time()
        self._last_error = None
        return {"text": content.strip(), "latency_seconds": round(elapsed, 4),
                "input_tokens": int(usage.get("prompt_tokens") or 0),
                "output_tokens": int(usage.get("completion_tokens") or 0),
                "model_id": self._model_name, "provider": "colibri",
                "device": "managed-by-colibri", "dtype": "hierarchical"}

    def chat(self, message: str, system: str = "You are a helpful assistant.",
             max_new_tokens: int = 512, temperature: float = 0.2) -> dict[str, Any]:
        if not message.strip():
            raise ValueError("message must not be empty")
        return self._generate([{"role": "system", "content": system},
                               {"role": "user", "content": message}],
                              max_new_tokens, temperature)

    def decompose(self, prompt: str, context: str = "", max_new_tokens: int = 1200,
                  agent_context: dict[str, Any] | None = None) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        try:
            system = build_analyst_system_prompt(agent_context)
        except RuntimeError as exc:
            raise ModelRuntimeError(str(exc)) from exc
        user = "Objective:\n" + prompt.strip()
        if context.strip():
            user += "\n\nAdditional context:\n" + context.strip()
        result = self._generate([{"role": "system", "content": system},
                                 {"role": "user", "content": user}],
                                max_new_tokens, 0.0)
        parsed, error = parse_goal_spec_response(result["text"])
        result.update({"goal_spec": parsed, "json_valid": parsed is not None,
                       "parse_error": error,
                       "semantic_diagnostics": diagnose_goal_spec(prompt, parsed) if parsed is not None else [],
                       "semantic_correctness_verified": False})
        result["semantic_review_required"] = bool(result["semantic_diagnostics"])
        return result


_colibri_runtime = ColibriModelRuntime()


def get_colibri_runtime() -> ColibriModelRuntime:
    return _colibri_runtime
