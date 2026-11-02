from types import SimpleNamespace

from taas.certificate import Certificate
from taas.composer import ComposeResult
from taas.engine import DiscoveryEngine, EngineConfig


def certificate(valid=True):
    checks = {name: valid for name in ("S", "C", "P", "E", "L", "V")}
    return Certificate([], checks, {}, "exact", 0.0, 1.0, 0.0, {})


class FakeComposer:
    def __init__(self, result):
        self.result = result

    def compose(self, *args):
        return self.result


def engine_for(monkeypatch, result, gap):
    import taas.engine as engine_module

    engine = DiscoveryEngine.__new__(DiscoveryEngine)
    engine.cfg = EngineConfig(refine_k=0)
    engine.gap = lambda spec: gap
    engine.composer = FakeComposer(result)
    engine.H = object()
    monkeypatch.setattr(engine_module, "manifest", lambda H, cert: {"certified": True})
    return engine


def test_discover_abstains_when_composition_has_no_certificate(monkeypatch):
    result = ComposeResult(["tool-a"], None, None)
    engine = engine_for(monkeypatch, result, SimpleNamespace(clarify=None, gap=[object()]))

    found = engine.discover(object(), policy=object())

    assert found.abstained
    assert found.toolkit is None
    assert found.certificate is None
    assert found.counterexample.check == "CERTIFICATE"
    assert found.counterexample.witness["failed_checks"] == ["missing_certificate"]
    assert found.manifest is None


def test_discover_abstains_when_mandatory_certificate_check_fails(monkeypatch):
    result = ComposeResult(["tool-a"], certificate(valid=False), None)
    engine = engine_for(monkeypatch, result, SimpleNamespace(clarify=None, gap=[object()]))

    found = engine.discover(object(), policy=object())

    assert found.abstained
    assert found.toolkit is None
    assert found.counterexample.check == "CERTIFICATE"
    assert found.counterexample.witness["failed_checks"] == ["S", "C", "P", "E", "L", "V"]


def test_discover_preserves_legitimate_empty_toolkit_with_valid_certificate(monkeypatch):
    result = ComposeResult([], certificate(valid=True), None)
    engine = engine_for(monkeypatch, result, SimpleNamespace(clarify=None, gap=[]))

    found = engine.discover(object(), policy=object())

    assert not found.abstained
    assert found.toolkit == []
    assert found.certificate.valid
    assert found.manifest == {"certified": True}
