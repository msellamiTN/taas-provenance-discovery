"""Process-local Hugging Face text-generation runtime for TaaS Studio.

Models are loaded only on explicit user action. Remote repository code is never
executed. This runtime is single-process/single-user oriented; production
multi-user deployments need isolated workers and resource scheduling.
"""
from __future__ import annotations

import re
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from json import JSONDecoder, JSONDecodeError
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


class ModelRuntimeError(RuntimeError):
    """A model could not be loaded or used safely."""



def parse_goal_spec_response(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse one canonical GoalSpec object; never repair generic model output."""
    if not isinstance(raw, str) or not raw.strip():
        return None, "The model returned an empty response."
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    if start < 0:
        return None, "No JSON object was found in the model response."
    try:
        parsed, end = JSONDecoder().raw_decode(text[start:])
    except JSONDecodeError as exc:
        return None, f"Invalid JSON at character {start + exc.pos}: {exc.msg}."
    if not isinstance(parsed, dict):
        return None, "The response must be one JSON object."
    if text[start + end:].strip():
        return None, "Unexpected content follows the JSON object."
    if not isinstance(parsed.get("prompt_inputs"), list) or not isinstance(parsed.get("goals"), list):
        return None, "Missing canonical prompt_inputs/goals arrays; generic id/query/context output is not a GoalSpec."
    unsupported = set(parsed) - {"prompt", "prompt_inputs", "goals"}
    if unsupported:
        return None, "Unsupported top-level field(s): " + ", ".join(sorted(unsupported))
    return parsed, None



def diagnose_goal_spec(prompt: str, spec: dict[str, Any]) -> list[dict[str, str]]:
    """Return conservative deterministic warnings; this is not a semantic verifier."""
    objective = (prompt or spec.get("prompt") or "").casefold()
    goals = spec.get("goals", []) if isinstance(spec, dict) else []
    classes = {str(g.get("class", "")).casefold() for g in goals if isinstance(g, dict)}
    diagnostics: list[dict[str, str]] = []
    total_requested = bool(re.search(r"\b(sum|summation|aggregate|total value|sum of|calculate\s+(?:the\s+)?total)\b", objective))
    if total_requested and not ({"aggregate", "compute_exact"} & classes):
        diagnostics.append({"code":"missing_aggregation","severity":"error","message":"The objective requests a total or sum, but no aggregate/compute_exact goal is present. A summary is not a calculation.","suggestion":"Add an aggregate or compute_exact goal that consumes numeric values and produces number."})
    if total_requested and ({"aggregate", "compute_exact"} & classes):
        aggregation_outputs = [
            str(g.get("out", "")).casefold() for g in goals
            if isinstance(g, dict) and str(g.get("class", "")).casefold() in {"aggregate", "compute_exact"}
        ]
        if not any(value == "number" or value.startswith("number:") for value in aggregation_outputs):
            diagnostics.append({"code":"aggregation_output_not_numeric","severity":"error","message":"The objective requests a numeric total, but no proposed goal declares a numeric output.","suggestion":"Set the aggregation result type to number."})
        exact_goals = [g for g in goals if isinstance(g, dict) and str(g.get("class", "")).casefold() in {"aggregate", "compute_exact"}]
        if exact_goals and any(str(g.get("exactness", "tolerant")).casefold() != "exact" for g in exact_goals):
            diagnostics.append({"code":"aggregation_not_exact","severity":"warning","message":"The requested total is exact, but an aggregation goal is marked tolerant.","suggestion":"Use exactness='exact' unless approximation is explicitly permitted."})
    if total_requested and "summarise" in classes and not ({"aggregate", "compute_exact"} & classes):
        diagnostics.append({"code":"summary_substituted_for_calculation","severity":"error","message":"A summarise goal appears where the objective requires arithmetic aggregation.","suggestion":"Add numeric aggregation; keep summarisation only as an optional presentation step."})
    if total_requested and re.search(r"\b(all|every)\b", objective):
        retrievals = [g for g in goals if isinstance(g, dict) and str(g.get("class", "")).casefold() in {"retrieve", "search", "fetch_web"}]
        if any(isinstance(g.get("n"), (int, float)) and not isinstance(g.get("n"), bool) and g.get("n") > 1 for g in retrievals):
            diagnostics.append({"code":"scope_completeness_unproven","severity":"warning","message":"The objective says all/every, but a finite n value is only an estimate and does not prove complete retrieval.","suggestion":"Preserve unbounded scope in retrieval description; treat n as an estimate, not a completeness guarantee."})
    has_currency_context = bool(re.search(r"\b(usd|eur|gbp|tnd|currency|currencies|same currency|convert)\b", objective))
    if total_requested and not has_currency_context and re.search(r"\b(transaction|transactions|financial|payment|payments)\b", objective):
        diagnostics.append({"code":"currency_policy_unspecified","severity":"warning","message":"The financial aggregation does not state how multiple currencies are handled.","suggestion":"Confirm one currency, a conversion policy, or totals grouped by currency when mixed currencies are possible."})
    return diagnostics


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
                try:
                    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=False, use_fast=True)
                except Exception as fast_exc:
                    try:
                        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=False, use_fast=False)
                    except Exception as slow_exc:
                        raise ModelRuntimeError(
                            "Tokenizer loading failed in fast and slow modes. Install sentencepiece and tiktoken: "
                            "pip install sentencepiece tiktoken. "
                            f"Fast tokenizer: {type(fast_exc).__name__}: {fast_exc}; "
                            f"slow tokenizer: {type(slow_exc).__name__}: {slow_exc}"
                        ) from slow_exc
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
                    "provider": "huggingface",
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
            + "\n\nPRIORITY SEMANTIC RULES: preserve the requested operation. Calculating a total or sum requires aggregate or compute_exact with numeric output; summarise is not aggregation. Use exactness=exact for exact arithmetic. Preserve all/every scope; n is not proof of completeness. Surface currency ambiguity for financial totals."
            + "\n\nSTRICT OUTPUT: exactly one JSON object with only prompt (optional), "
              "prompt_inputs (array), and goals (array). Do not emit id/query/context wrappers, "
              "Markdown fences, or commentary. Never claim semantic correctness is verified."
        )
        user_content = "Objective:\n" + prompt.strip()
        if context.strip():
            user_content += "\n\nAdditional context:\n" + context.strip()
        result = self._generate(
            [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
            max_new_tokens, 0.0,
        )
        parsed, parse_error = parse_goal_spec_response(result["text"])
        result["goal_spec"] = parsed
        result["json_valid"] = parsed is not None
        result["parse_error"] = parse_error
        result["semantic_diagnostics"] = diagnose_goal_spec(prompt, parsed) if parsed is not None else []
        result["semantic_review_required"] = bool(result["semantic_diagnostics"])
        result["semantic_correctness_verified"] = False
        return result


_runtime = HuggingFaceModelRuntime()


def get_model_runtime() -> HuggingFaceModelRuntime:
    return _runtime
