import numpy as np
import pytest

from experiments.e8_cpu_static_embedding import (
    build_idf, encode_text, rank_embeddings, rank_embeddings_checkpointed,
    tokenize, train_fasttext,
)
from experiments.e8_retrieval_campaign import ToolDocument


class FakeFastText:
    def get_word_vector(self, word):
        table = {"search": [1, 0, 0], "customer": [0, 1, 0],
                 "invoice": [0, 0, 1], "unseen_api": [1, 1, 0]}
        return np.asarray(table.get(word, [0.1, 0.1, 0.1]), dtype=np.float32)


def test_tokenizer_splits_case_and_keeps_underscores():
    assert tokenize("Search Customer_ID APIv2") == ["search", "customer_id", "apiv2"]


def test_idf_is_computed_over_documents_only_and_smoothed():
    idf, n = build_idf(["search customer", "search invoice"])
    assert n == 2
    assert idf["search"] == pytest.approx(1.0)
    assert idf["customer"] == pytest.approx(np.log(3 / 2) + 1)


def test_encode_text_returns_unit_vector_and_explicit_stats():
    vector, stats = encode_text("search customer", FakeFastText(),
                                {"search": 1, "customer": 2}, 3)
    assert np.linalg.norm(vector) == pytest.approx(1.0)
    assert vector[1] > vector[0]
    assert stats == {"tokens": 2, "weighted_tokens": 2, "zero_vector": 0}


def test_oov_token_uses_fasttext_subword_lookup_interface():
    vector, stats = encode_text("unseen_api", FakeFastText(), {}, 3)
    assert np.linalg.norm(vector) == pytest.approx(1.0)
    assert stats["zero_vector"] == 0


def test_empty_query_is_explicit_zero_vector_not_arbitrary_rank():
    vector, stats = encode_text("!!!", FakeFastText(), {}, 3)
    assert np.array_equal(vector, np.zeros(3, dtype=np.float32))
    assert stats["zero_vector"] == 1


def test_rank_embeddings_is_exact_stable_and_abstains_on_zero():
    q = np.asarray([[1, 0, 0], [0, 0, 0]], dtype=np.float32)
    d = np.asarray([[0, 1, 0], [1, 0, 0]], dtype=np.float32)
    assert rank_embeddings(q, d, ["b", "a"], top_k=2) == [["a", "b"], []]


def test_rank_embeddings_rejects_bad_shapes_and_nonfinite():
    with pytest.raises(ValueError, match="dimensions"):
        rank_embeddings(np.ones((1, 2)), np.ones((1, 3)), ["x"])
    with pytest.raises(ValueError, match="non-finite"):
        rank_embeddings(np.asarray([[np.nan]]), np.ones((1, 1)), ["x"])


def test_checkpoint_resume_and_fingerprint_validation(tmp_path):
    q = np.asarray([[1, 0], [0, 1], [1, 1]], dtype=np.float32)
    d = np.asarray([[1, 0], [0, 1]], dtype=np.float32)
    ids, tasks = ["a", "b"], ["q1", "q2", "q3"]
    first = rank_embeddings_checkpointed(q, d, ids, tasks, tmp_path, "fp", 2, 2)
    second = rank_embeddings_checkpointed(q, d, ids, tasks, tmp_path, "fp", 2, 2)
    assert first == second and list(first) == tasks
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        rank_embeddings_checkpointed(q, d, ids, tasks, tmp_path, "changed", 2, 2)


def test_train_fasttext_fails_closed_when_dependency_missing(monkeypatch, tmp_path):
    import sys
    monkeypatch.setitem(sys.modules, "fasttext", None)
    docs = [ToolDocument("s::a", "search customer", "test", "s")]
    with pytest.raises(RuntimeError, match="fasttext-wheel"):
        train_fasttext(docs, tmp_path / "model.bin")
