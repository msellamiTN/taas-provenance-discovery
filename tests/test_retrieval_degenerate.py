import warnings

import numpy as np
import pytest

from taas.retrieval import LSAEncoder


@pytest.mark.parametrize(
    "documents",
    [
        ["list orders for a customer"],
        ["same capability description", "same capability description"],
    ],
)
def test_lsa_encoder_handles_zero_variance_corpora_without_runtime_warning(documents):
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", RuntimeWarning)
        encoder = LSAEncoder().fit(documents)
        vectors = encoder.encode(["list orders", "customer orders"])

    assert not [w for w in captured if issubclass(w.category, RuntimeWarning)]
    assert encoder._use_svd is False
    assert vectors.ndim == 2
    assert vectors.shape[0] == 2
    assert np.isfinite(vectors).all()
    assert np.isfinite(vectors @ vectors.T).all()
    assert np.all(np.linalg.norm(vectors, axis=1) <= 1.0 + 1e-9)


def test_lsa_encoder_keeps_svd_for_non_degenerate_corpora():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", RuntimeWarning)
        encoder = LSAEncoder().fit([
            "list customer orders",
            "delete an invoice",
            "search product catalogue",
        ])
        vectors = encoder.encode(["list orders"])

    assert not [w for w in captured if issubclass(w.category, RuntimeWarning)]
    assert encoder._use_svd is True
    assert vectors.shape[0] == 1
    assert np.isfinite(vectors).all()
