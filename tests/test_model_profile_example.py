import json
from pathlib import Path

from taas.model_profile import ModelProfile


def test_strict_empty_profile_loads_and_does_not_claim_unmeasured_capabilities():
    path = Path(__file__).parents[1] / "examples" / "model_profiles" / "strict-empty.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    profile = ModelProfile.load(path)

    assert profile.model_id == raw["model_id"]
    assert profile.tau == 0.9
    assert profile.strict is True
    assert profile.classes == {}
    # Empty calibration is intentionally fail-closed: unknown capabilities are not native.
    assert profile.rho("summarise", n=1, lang="en") == 0.0
    assert profile.rho("retrieve", n=1, lang="en") == 0.0
