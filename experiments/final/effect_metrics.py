"""Correct evaluation of binary predictions with explicit missing/unknown states."""
from __future__ import annotations

from typing import Sequence


def confusion_with_unknown(predictions: Sequence[bool | None],
                           reference: Sequence[bool]) -> dict:
    """Return confusion metrics without coercing missing predictions to negatives.

    Precision, recall and discrepancy_rate are conditional on records with a known
    prediction. unsafe_reference_coverage reports how much of the reference-unsafe
    population has a known prediction; unsafe_capture_rate_all uses the entire
    reference-unsafe population as denominator, so unknown unsafe records are not
    silently credited as detected.
    """
    if len(predictions) != len(reference):
        raise ValueError("predictions and reference must have the same length")
    if any(p is not None and not isinstance(p, bool) for p in predictions):
        raise TypeError("predictions must contain only bool or None")
    if any(not isinstance(r, bool) for r in reference):
        raise TypeError("reference must contain only bool values")

    known = [(p, r) for p, r in zip(predictions, reference) if p is not None]
    unknown = [(p, r) for p, r in zip(predictions, reference) if p is None]

    tp = sum(p is True and r is True for p, r in known)
    fp = sum(p is True and r is False for p, r in known)
    fn = sum(p is False and r is True for p, r in known)
    tn = sum(p is False and r is False for p, r in known)
    unknown_unsafe = sum(r is True for _, r in unknown)
    unknown_safe = sum(r is False for _, r in unknown)
    known_unsafe = tp + fn
    known_safe = fp + tn
    total_unsafe = sum(r is True for r in reference)

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "unknown": len(unknown),
        "n_total": len(reference),
        "n_evaluated": len(known),
        "coverage": len(known) / len(reference) if reference else 0.0,
        "known_unsafe": known_unsafe,
        "known_safe": known_safe,
        "unknown_unsafe": unknown_unsafe,
        "unknown_safe": unknown_safe,
        "unsafe_reference_coverage": (known_unsafe / total_unsafe) if total_unsafe else None,
        "unsafe_capture_rate_all": (tp / total_unsafe) if total_unsafe else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / known_unsafe if known_unsafe else None,
        "discrepancy_rate": ((fp + fn) / len(known)) if known else None,
        "evaluation_scope": "covered_only",
    }
