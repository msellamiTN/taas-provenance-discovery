"""Unit tests for the colibri provider adapter (mocked HTTP — no server)."""
from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest

from taas.studio import colibri_runtime
from taas.studio.colibri_runtime import ColibriModelRuntime
from taas.studio.model_runtime import ModelRuntimeError


class _Resp:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_urlopen(monkeypatch, payload=None, raise_exc=None):
    def fake(request, timeout=30):
        if raise_exc is not None:
            raise raise_exc
        return _Resp(payload or {})
    monkeypatch.setattr(colibri_runtime, "urlopen", fake)


@pytest.fixture
def rt(monkeypatch):
    monkeypatch.setenv("TAAS_COLIBRI_BASE_URL", "http://127.0.0.1:8090/v1")
    return ColibriModelRuntime()


def test_status_available(rt, monkeypatch):
    _patch_urlopen(monkeypatch, {"data": [{"id": "qwen3-coder-30b"}]})
    s = rt.status()
    assert s["provider"] == "colibri" and s["available"] is True
    assert s["models"] == [{"name": "qwen3-coder-30b"}]
    assert s["placement"] == "hot-experts-gpu / warm-ram / cold-nvme"


def test_status_unreachable_is_honest(rt, monkeypatch):
    _patch_urlopen(monkeypatch, raise_exc=OSError("refused"))
    s = rt.status()
    assert s["available"] is False and "Cannot reach Colibri" in s["last_error"]


def test_load_selects_served_model(rt, monkeypatch):
    _patch_urlopen(monkeypatch, {"data": [{"id": "qwen3-coder-30b"}]})
    out = rt.load("qwen3-coder-30b")
    assert out["model_selected"] == "qwen3-coder-30b"


def test_load_rejects_unknown_model(rt, monkeypatch):
    _patch_urlopen(monkeypatch, {"data": [{"id": "other"}]})
    with pytest.raises(ModelRuntimeError, match="not served"):
        rt.load("qwen3-coder-30b")


def test_load_rejects_bad_name(rt):
    with pytest.raises(ValueError):
        rt.load("has whitespace")


def test_chat_real_response_shape(rt, monkeypatch):
    _patch_urlopen(monkeypatch, {
        "data": [{"id": "m"}],
        "choices": [{"message": {"content": "OK"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1}})
    rt.load("m")
    out = rt.chat("ping", max_new_tokens=8)
    assert out["text"] == "OK" and out["provider"] == "colibri"
    assert out["input_tokens"] == 5 and out["output_tokens"] == 1
    assert out["device"] == "managed-by-colibri"


def test_chat_requires_selected_model(rt):
    with pytest.raises(ModelRuntimeError, match="Select a colibri model"):
        rt.chat("ping")


def test_chat_bounds(rt):
    with pytest.raises(ValueError):
        rt.chat("x", max_new_tokens=0)
    with pytest.raises(ValueError):
        rt.chat("x", temperature=3.0)


def test_chat_empty_message(rt):
    with pytest.raises(ValueError):
        rt.chat("   ")


def test_http_error_wrapped(rt, monkeypatch):
    _patch_urlopen(monkeypatch,
                   raise_exc=HTTPError("http://x", 500, "err", {}, io.BytesIO(b"boom")))
    s = rt.status()
    assert s["available"] is False and "Colibri HTTP 500" in s["last_error"]


def test_decompose_parses_goalspec(rt, monkeypatch):
    spec = json.dumps({"name": "list-orders", "objective": "x",
                       "constraints": [], "tools": []})
    _patch_urlopen(monkeypatch, {
        "data": [{"id": "m"}],
        "choices": [{"message": {"content": spec}}]})
    rt.load("m")
    out = rt.decompose("list orders")
    assert out["provider"] == "colibri"
    assert "json_valid" in out and "semantic_diagnostics" in out


def test_base_url_validation(monkeypatch):
    monkeypatch.setenv("TAAS_COLIBRI_BASE_URL", "http://u:p@host/v1")
    with pytest.raises(ModelRuntimeError, match="embedded credentials"):
        ColibriModelRuntime()._base_url()
