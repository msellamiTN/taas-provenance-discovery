from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "final"))
from effect_metrics import confusion_with_unknown  # noqa: E402


def test_unknown_predictions_are_not_counted_as_false_negatives_or_true_negatives():
    result = confusion_with_unknown(
        [False, False, None, None],
        [True, False, True, False],
    )

    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (0, 0, 1, 1)
    assert result["unknown"] == 2
    assert result["unknown_unsafe"] == 1
    assert result["unknown_safe"] == 1
    assert result["n_evaluated"] == 2
    assert result["coverage"] == pytest.approx(0.5)
    assert result["unsafe_reference_coverage"] == pytest.approx(0.5)
    assert result["unsafe_capture_rate_all"] == pytest.approx(0.0)
    assert result["recall"] == pytest.approx(0.0)
    assert result["discrepancy_rate"] == pytest.approx(0.5)


def test_all_known_predictions_match_standard_binary_confusion_metrics():
    result = confusion_with_unknown(
        [True, True, False, False],
        [True, False, True, False],
    )

    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 1, 1, 1)
    assert result["unknown"] == 0
    assert result["coverage"] == pytest.approx(1.0)
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["discrepancy_rate"] == pytest.approx(0.5)


def test_zero_coverage_returns_undefined_conditional_metrics():
    result = confusion_with_unknown([None, None], [True, False])

    assert result["n_evaluated"] == 0
    assert result["coverage"] == 0.0
    assert result["unknown_unsafe"] == 1
    assert result["unknown_safe"] == 1
    assert result["precision"] is None
    assert result["recall"] is None
    assert result["discrepancy_rate"] is None
    assert result["unsafe_reference_coverage"] == 0.0
    assert result["unsafe_capture_rate_all"] == 0.0


def test_mismatched_lengths_are_rejected():
    with pytest.raises(ValueError, match="same length"):
        confusion_with_unknown([True], [True, False])


def test_non_boolean_predictions_are_rejected():
    with pytest.raises(TypeError, match="bool or None"):
        confusion_with_unknown([1], [True])


def test_non_boolean_reference_is_rejected():
    with pytest.raises(TypeError, match="reference"):
        confusion_with_unknown([True], [1])
