from __future__ import annotations

import sys
import types

from taas.studio.model_runtime import HuggingFaceModelRuntime


def test_huggingface_runtime_falls_back_to_slow_tokenizer(monkeypatch):
    calls = []

    class Tokenizer:
        pad_token_id = 0
        eos_token_id = 0
        pad_token = None

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(model_id, **kwargs):
            calls.append(kwargs.get("use_fast"))
            if kwargs.get("use_fast") is True:
                raise ValueError("fast tokenizer backend could not be instantiated")
            return Tokenizer()

    class Model:
        def to(self, device):
            self.device = device
        def eval(self):
            return None

    class AutoModelForCausalLM:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            return Model()

    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    fake_torch.float32 = "float32"
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = AutoTokenizer
    fake_transformers.AutoModelForCausalLM = AutoModelForCausalLM
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    runtime = HuggingFaceModelRuntime()
    state = runtime.load("Qwen/Qwen2.5-0.5B-Instruct", device="cpu")
    assert calls == [True, False]
    assert state["model_loaded"] is True
    assert state["device"] == "cpu"
    assert state["provider"] == "huggingface"
