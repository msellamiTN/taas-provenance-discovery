from taas.experiments.registry_typing_evaluators import (
    registry_characterization, semantic_typing_metrics, typing_threshold_curve,
)


def test_registry_characterization_reports_duplicate_and_metadata_coverage():
    result = registry_characterization([
        {"tool_id": "a", "server": "s1", "category": "data", "source": "x",
         "transport": "stdio", "definition_hash": "h1", "annotations": {"readOnlyHint": True},
         "description": "read"},
        {"tool_id": "a", "server": "s1", "category": "data", "source": "x",
         "transport": "stdio", "definition_hash": "h1", "annotations": None,
         "description": ""},
    ])
    assert result["n_rows"] == 2
    assert result["duplicate_tool_rows"] == 1
    assert result["annotation_coverage"]["rate"] == .5


def test_semantic_typing_metrics_report_kappa_and_abstention():
    result = semantic_typing_metrics(
        {"a": "read", "b": "write", "c": "read"},
        {"a": {"label": "read", "confidence": .9},
         "b": {"label": "read", "confidence": .8},
         "c": {"label": "read", "confidence": .2}},
        confidence_threshold=.5,
    )
    assert result["prediction_abstentions"] == 1
    assert result["confusion_matrix"]["write"]["read"] == 1
    assert result["cohen_kappa"] is not None


def test_typing_threshold_curve_preserves_fixed_reference_denominator():
    rows = typing_threshold_curve(
        {"a": "read", "b": "write"},
        {"a": {"label": "read", "confidence": .9},
         "b": {"label": "write", "confidence": .4}},
        [.3, .8],
    )
    assert rows[0]["labelled_denominator"] == rows[1]["labelled_denominator"] == 2
    assert rows[1]["prediction_abstentions"] == 1
