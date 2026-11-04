"""Ollama adapter for the TaaS Studio model-runtime interface."""
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
    ModelRuntimeError, ROOT, diagnose_goal_spec, parse_goal_spec_response,
)


class OllamaModelRuntime:
    """Calls an operator-configured Ollama HTTP endpoint; never shells out."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model_name: str | None = None
        self._last_inference_at: float | None = None
        self._last_error: str | None = None

    @staticmethod
    def _base_url() -> str:
        value = os.environ.get("TAAS_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ModelRuntimeError("TAAS_OLLAMA_BASE_URL must be an http(s) URL without embedded credentials")
        return value

    def _request(self, path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self._base_url() + path, data=data,
                          headers={"Content-Type": "application/json"} if data else {})
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ModelRuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ModelRuntimeError(f"Cannot reach Ollama at {self._base_url()}. Start Ollama and verify TAAS_OLLAMA_BASE_URL. {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelRuntimeError(f"Ollama returned invalid JSON: {exc}") from exc
        if not isinstance(result, dict):
            raise ModelRuntimeError("Ollama returned an unexpected response shape")
        return result

    def status(self) -> dict[str, Any]:
        try:
            payload = self._request("/api/tags", timeout=4)
            return {
                "provider": "ollama", "available": True, "base_url": self._base_url(),
                "model_selected": self._model_name,
                "models": [{"name": x.get("name"), "size": x.get("size")}
                           for x in payload.get("models", []) if isinstance(x, dict)],
                "last_inference_at": self._last_inference_at, "last_error": self._last_error,
                "execution_performed": False,
            }
        except ModelRuntimeError as exc:
            return {"provider": "ollama", "available": False, "base_url": self._base_url(),
                    "model_selected": self._model_name, "models": [],
                    "last_inference_at": self._last_inference_at, "last_error": str(exc),
                    "execution_performed": False}

    def load(self, model_id: str, device: str = "auto") -> dict[str, Any]:
        name = model_id.strip()
        if not name or len(name) > 256 or any(ch.isspace() for ch in name):
            raise ValueError("Ollama model name must be a non-empty model tag without whitespace")
        self._request("/api/show", {"name": name}, timeout=20)
        with self._lock:
            self._model_name = name
            self._last_error = None
        result = self.status()
        result["model_selected"] = name
        result["load_semantics"] = "validated; Ollama loads weights on first inference"
        return result

    def _generate(self, messages: list[dict[str, str]], max_new_tokens: int, temperature: float) -> dict[str, Any]:
        if not 1 <= max_new_tokens <= 2048:
            raise ValueError("max_new_tokens must be between 1 and 2048")
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if not self._model_name:
            raise ModelRuntimeError("Select an installed Ollama model before inference")
        started = time.perf_counter()
        result = self._request("/api/chat", {
            "model": self._model_name, "messages": messages, "stream": False,
            "options": {"num_predict": max_new_tokens, "temperature": temperature},
        }, timeout=600)
        elapsed = time.perf_counter() - started
        content = result.get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise ModelRuntimeError("Ollama response did not contain message.content")
        self._last_inference_at = time.time()
        self._last_error = None
        return {"text": content.strip(), "latency_seconds": round(elapsed, 4),
                "input_tokens": int(result.get("prompt_eval_count", 0) or 0),
                "output_tokens": int(result.get("eval_count", 0) or 0),
                "model_id": self._model_name, "provider": "ollama",
                "device": "managed-by-ollama", "dtype": "managed-by-ollama"}

    def chat(self, message: str, system: str = "You are a helpful assistant.",
             max_new_tokens: int = 512, temperature: float = 0.2) -> dict[str, Any]:
        if not message.strip():
            raise ValueError("message must not be empty")
        return self._generate([{"role": "system", "content": system},
                               {"role": "user", "content": message}],
                              max_new_tokens, temperature)

    def decompose(self, prompt: str, context: str = "", max_new_tokens: int = 1200) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        guide = ROOT / "docs" / "ANALYST_GUIDE.md"
        theta = ROOT / "data" / "processed" / "theta.json"
        if not guide.is_file() or not theta.is_file():
            raise ModelRuntimeError("Analyst guide or semantic type vocabulary is missing")
        system = (guide.read_text(encoding="utf-8") + "\n\nSemantic type vocabulary (Θ):\n"
                  + theta.read_text(encoding="utf-8")
                  + "\n\nPRIORITY RULES: preserve the requested operation. A total requires aggregate or compute_exact with numeric output; summarise is not aggregation. Use exactness=exact for exact arithmetic. Preserve all/every scope; n is not proof of completeness. Surface currency ambiguity."
                  + "\n\nSTRICT OUTPUT: exactly one canonical GoalSpec JSON object; no wrappers, fences, or commentary.")
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


_ollama_runtime = OllamaModelRuntime()


def get_ollama_runtime() -> OllamaModelRuntime:
    return _ollama_runtime
