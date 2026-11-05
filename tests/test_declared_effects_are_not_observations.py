from taas.data.registries import RawTool
from taas.experiments.registry_baselines import run_effect_baseline


def _tool(annotations):
    return RawTool(
        server="fixture",
        name="example",
        description="Fixture tool",
        input_schema={},
        annotations=annotations,
    )


def test_read_only_false_is_not_converted_to_write():
    result = run_effect_baseline("effects_declared", [_tool({"readOnlyHint": False})])
    row = result["predictions"][0]
    assert row["effects"] == []
    assert row["read_only_hint"] is False
    assert row["observed_effects"] is None
    assert row["evidence_class"] == "declared"


def test_missing_hints_remain_unknown_declarations():
    result = run_effect_baseline("effects_declared", [_tool({})])
    row = result["predictions"][0]
    assert row["read_only_hint"] is None
    assert row["destructive_hint"] is None
    assert row["open_world_hint"] is None
    assert row["effects"] == []
