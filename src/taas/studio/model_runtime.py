"""Process-local Hugging Face text-generation runtime for TaaS Studio.

Models are loaded only on explicit user action. Remote repository code is never
executed. This runtime is single-process/single-user oriented; production
multi-user deployments need isolated workers and resource scheduling.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


class ModelRuntimeError(RuntimeError):
    """A model could not be loaded or used safely."""


class HuggingFaceModelRuntime:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model = None
        self._tokenizer = None
        self._torch = None
        self._model_id: str | None = None
        self._device: str | None = None
        self._dtype: str | None = None
        self._loaded_at: float | None = None
        self._last_inference_at: float | None = None
        self._last_error: str | None = None

    @staticmethod
    def _validate_model_id(model_id: str) -> str:
        value = model_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
            raise ValueError("model_id must be a Hugging Face repository ID in owner/name form")
        return value

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "model_loaded": self._model is not None,
                "model_id": self._model_id,
                "device": self._device,
                "dtype": self._dtype,
                "loaded_at": self._loaded_at,
                "inference_executed": self._last_inference_at is not None,
                "last_inference_at": self._last_inference_at,
                "last_error": self._last_error,
                "trust_remote_code": False,
                "runtime_scope": "single-process",
            }

    def load(self, model_id: str, device: str = "auto") -> dict[str, Any]:
        model_id = self._validate_model_id(model_id)
        if device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be auto, cpu or cuda")
        with self._lock:
            if self._model is not None and self._model_id == model_id and (device == "auto" or device == self._device):
                return self.status()
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError as exc:
                self._last_error = "Install the optional Hugging Face runtime: pip install -e '.[hf]'"
                raise ModelRuntimeError(self._last_error) from exc

            cuda_available = bool(torch.cuda.is_available())
            if device == "cuda" and not cuda_available:
                raise ModelRuntimeError("CUDA was requested but torch.cuda.is_available() is false")
            target = "cuda" if (device == "cuda" or (device == "auto" and cuda_available)) else "cpu"
            dtype = torch.float32
            if target == "cuda":
                dtype = torch.bfloat16 if getattr(torch.cuda, "is_bf16_supported", lambda: False)() else torch.float16

            # Do not discard a working model until the replacement has loaded.
            self._last_error = None
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=False)
                if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
                    tokenizer.pad_token = tokenizer.eos_token
                model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    torch_dtype=dtype,
                    low_cpu_mem_usage=True,
                    trust_remote_code=False,
                    use_safetensors=True,
                )
                model.to(target)
                model.eval()
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                raise ModelRuntimeError(self._last_error) from exc

            self._model, self._tokenizer, self._torch = model, tokenizer, torch
            self._model_id, self._device, self._dtype = model_id, target, str(dtype).replace("torch.", "")
            self._loaded_at = time.time()
            self._last_inference_at = None
            return self.status()

    def _generate(self, messages: list[dict[str, str]], max_new_tokens: int, temperature: float) -> dict[str, Any]:
        if not 1 <= max_new_tokens <= 2048:
            raise ValueError("max_new_tokens must be between 1 and 2048")
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        with self._lock:
            if self._model is None or self._tokenizer is None:
                raise ModelRuntimeError("No model is loaded. Load a Hugging Face model first.")
            tokenizer, model, torch = self._tokenizer, self._model, self._torch
            try:
                if getattr(tokenizer, "chat_template", None):
                    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                    inputs = tokenizer(prompt, return_tensors="pt")
                else:
                    prompt = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages) + "\nASSISTANT:"
                    inputs = tokenizer(prompt, return_tensors="pt")
                inputs = {key: value.to(self._device) for key, value in inputs.items()}
                generation = {"max_new_tokens": max_new_tokens, "do_sample": temperature > 0}
                if temperature > 0:
                    generation["temperature"] = temperature
                    generation["top_p"] = 0.9
                started = time.perf_counter()
                with torch.inference_mode():
                    output = model.generate(**inputs, **generation)
                elapsed = time.perf_counter() - started
                generated = output[0][inputs["input_ids"].shape[1]:]
                text = tokenizer.decode(generated, skip_special_tokens=True).strip()
                self._last_inference_at = time.time()
                return {
                    "text": text,
                    "latency_seconds": round(elapsed, 4),
                    "input_tokens": int(inputs["input_ids"].shape[1]),
                    "output_tokens": int(generated.shape[0]),
                    "model_id": self._model_id,
                    "device": self._device,
                    "dtype": self._dtype,
                }
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                raise ModelRuntimeError(self._last_error) from exc

    def chat(self, message: str, system: str = "You are a helpful assistant.", max_new_tokens: int = 512,
             temperature: float = 0.2) -> dict[str, Any]:
        if not message.strip():
            raise ValueError("message must not be empty")
        return self._generate(
            [{"role": "system", "content": system}, {"role": "user", "content": message}],
            max_new_tokens, temperature,
        )

    def decompose(self, prompt: str, context: str = "", max_new_tokens: int = 1200) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        guide_path = ROOT / "docs" / "ANALYST_GUIDE.md"
        theta_path = ROOT / "data" / "processed" / "theta.json"
        if not guide_path.is_file() or not theta_path.is_file():
            raise ModelRuntimeError("Analyst guide or semantic type vocabulary is missing from this installation")
        guide = guide_path.read_text(encoding="utf-8")
        theta = theta_path.read_text(encoding="utf-8")
        system = (
            guide + "\n\nSemantic type vocabulary (Θ):\n" + theta
            + "\nReturn only one JSON object matching the GoalSpec contract. "
              "Do not invent tools or claim that semantic correctness has been verified."
        )
        result = self._generate(
            [{"role": "system", "content": system},
             {"role": "user", "content": json.dumps({"id": "studio-agent", "query": prompt, "context": context}, ensure_ascii=False)}],
            max_new_tokens, 0.0,
        )
        raw = result["text"]
        match = re.search(r"\{.*\}", raw, re.S)
        try:
            parsed = json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            parsed = None
        result["goal_spec"] = parsed
        result["json_valid"] = isinstance(parsed, dict) and isinstance(parsed.get("goals"), list)
        result["semantic_correctness_verified"] = False
        return result


_runtime = HuggingFaceModelRuntime()


def get_model_runtime() -> HuggingFaceModelRuntime:
    return _runtime
