"""CPU-only FastText retrieval variant for the definitive PaMCP E8 tracks.

Separate from the original E8 runner. Reuses its frozen dataset loaders and
metric contract; never mutates original E8 code, data, checkpoints or results.
"""
from __future__ import annotations

import argparse
import hashlib
import gzip
import shutil
import urllib.request
import importlib.metadata
import json
import os
import platform
import re
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from experiments.e8_retrieval_campaign import (
    DiscoveryTask, ToolDocument, load_mcptoolbenchpp_track,
    load_toolret_track, _rank_scores,
)
from taas.experiments.evaluation_metrics import ranking_metrics

TOKEN_RE = re.compile(r"[a-z0-9_]+")
DEFAULT_CONFIG = {
    "model": "cc.en.300.bin", "model_url": "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.en.300.bin.gz",
    "dimension": 300, "top_k": 10, "checkpoint_tasks": 16, "min_free_disk_gb": 8.0,
}


def tokenize(text: str) -> list[str]:
    """Use the original E8 case-folded [a-z0-9_]+ tokenization."""
    return TOKEN_RE.findall(str(text).casefold())


def build_idf(documents: Sequence[str]) -> tuple[dict[str, float], int]:
    """Smoothed document-frequency IDF over tool documents only."""
    if not documents:
        raise ValueError("Cannot compute IDF from an empty tool corpus")
    df: Counter[str] = Counter()
    for text in documents:
        df.update(set(tokenize(text)))
    n_docs = len(documents)
    return ({t: float(np.log((n_docs + 1) / (freq + 1)) + 1.0)
             for t, freq in df.items()}, n_docs)


def _word_vector(model: Any, token: str, dimension: int) -> np.ndarray:
    vector = np.asarray(model.get_word_vector(token), dtype=np.float32)
    if vector.shape != (dimension,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"Invalid FastText vector for token {token!r}: {vector.shape}")
    return vector


def encode_text(text: str, model: Any, idf: Mapping[str, float],
                dimension: int) -> tuple[np.ndarray, dict[str, int]]:
    """IDF-weighted subword-aware mean pooling; zero queries abstain explicitly."""
    tokens = tokenize(text)
    if not tokens:
        return np.zeros(dimension, dtype=np.float32), {
            "tokens": 0, "weighted_tokens": 0, "zero_vector": 1}
    total = np.zeros(dimension, dtype=np.float64)
    weight_sum = 0.0
    for token in tokens:
        weight = float(idf.get(token, 1.0))
        if not np.isfinite(weight) or weight <= 0:
            raise ValueError(f"Invalid IDF weight for {token!r}")
        total += weight * _word_vector(model, token, dimension)
        weight_sum += weight
    vector = (total / weight_sum).astype(np.float32)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 1e-12:
        return np.zeros(dimension, dtype=np.float32), {
            "tokens": len(tokens), "weighted_tokens": len(tokens), "zero_vector": 1}
    vector /= norm
    return vector, {"tokens": len(tokens), "weighted_tokens": len(tokens),
                    "zero_vector": 0}


def encode_corpus(documents: Sequence[ToolDocument], model: Any, dimension: int):
    if not documents:
        raise ValueError("Tool corpus is empty")
    idf, n_docs = build_idf([d.text for d in documents])
    vectors = np.vstack([
        encode_text(d.text, model, idf, dimension)[0] for d in documents
    ]).astype(np.float32)
    if not np.all(np.linalg.norm(vectors, axis=1) > 1e-12):
        raise ValueError("At least one tool document produced a zero vector")
    return vectors, idf, {"documents": n_docs, "vocabulary_size": len(idf),
                          "zero_document_vectors": 0}


def encode_queries(tasks: Sequence[DiscoveryTask], model: Any,
                   idf: Mapping[str, float], dimension: int):
    vectors, zero, tokens = [], 0, 0
    for task in tasks:
        vector, stats = encode_text(task.query, model, idf, dimension)
        vectors.append(vector)
        zero += stats["zero_vector"]
        tokens += stats["tokens"]
    matrix = np.vstack(vectors).astype(np.float32) if vectors else np.empty((0, dimension), dtype=np.float32)
    return matrix, {"queries": len(tasks), "query_tokens": tokens,
                    "zero_query_vectors": zero}


def rank_embeddings(query_vectors: np.ndarray, tool_vectors: np.ndarray,
                    tool_ids: Sequence[str], top_k: int = 10) -> list[list[str]]:
    """Exact cosine ranking; normalized vectors make dot product equivalent."""
    if query_vectors.ndim != 2 or tool_vectors.ndim != 2:
        raise ValueError("Embeddings must be 2-D matrices")
    if query_vectors.shape[1] != tool_vectors.shape[1]:
        raise ValueError("Query and tool embedding dimensions differ")
    if tool_vectors.shape[0] != len(tool_ids):
        raise ValueError("Tool vector and identifier counts differ")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if not np.all(np.isfinite(query_vectors)) or not np.all(np.isfinite(tool_vectors)):
        raise ValueError("Embedding matrices contain non-finite values")
    ranked = []
    for query in query_vectors:
        if np.linalg.norm(query) <= 1e-12:
            ranked.append([])
        else:
            ranked.append(_rank_scores(tool_vectors @ query, tool_ids, top_k))
    return ranked


def rank_embeddings_checkpointed(query_vectors, tool_vectors, tool_ids,
                                  task_ids, checkpoint_dir, fingerprint,
                                  top_k=10, checkpoint_tasks=16):
    """Atomic, fingerprinted checkpoints; resume completed 16-query batches."""
    if len(task_ids) != query_vectors.shape[0] or len(set(task_ids)) != len(task_ids):
        raise ValueError("Task IDs must be unique and match query vectors")
    if checkpoint_tasks < 1:
        raise ValueError("checkpoint_tasks must be positive")
    directory = Path(checkpoint_dir)
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    for batch_no, start in enumerate(range(0, len(task_ids), checkpoint_tasks)):
        end = min(len(task_ids), start + checkpoint_tasks)
        ids = list(task_ids[start:end])
        path = directory / f"batch_{batch_no:05d}.json"
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("fingerprint") != fingerprint:
                raise ValueError(f"Checkpoint fingerprint mismatch: {path}")
            if payload.get("task_ids") != ids:
                raise ValueError(f"Checkpoint task IDs mismatch: {path}")
            batch = payload.get("rankings")
            if not isinstance(batch, dict) or set(batch) != set(ids):
                raise ValueError(f"Incomplete checkpoint: {path}")
        else:
            rows = rank_embeddings(query_vectors[start:end], tool_vectors, tool_ids, top_k)
            batch = dict(zip(ids, rows))
            payload = {"fingerprint": fingerprint, "batch_number": batch_no,
                       "task_ids": ids, "rankings": batch}
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        result.update(batch)
    return result


def download_pretrained_model(output_path: str | Path, url: str | None = None, min_free_gb: float = 8.0) -> dict[str, Any]:
    """Stream-decompress the official pretrained binary; never train or fine-tune."""
    target = Path(output_path); target.parent.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(target.parent).free / (1024 ** 3)
    if free_gb < min_free_gb:
        raise RuntimeError(f"Insufficient free disk: {free_gb:.2f} GiB available; {min_free_gb:.2f} GiB required")
    source = url or DEFAULT_CONFIG["model_url"]; temporary = target.with_name(target.name + ".part")
    try:
        request = urllib.request.Request(source, headers={"User-Agent": "TaaS-E8-v2/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            with gzip.GzipFile(fileobj=response, mode="rb") as compressed:
                with temporary.open("wb") as output:
                    shutil.copyfileobj(compressed, output, length=1024 * 1024)
                    output.flush(); os.fsync(output.fileno())
        if not temporary.is_file() or temporary.stat().st_size < 1024 * 1024:
            raise RuntimeError("Downloaded FastText model is unexpectedly small")
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True); raise
    return {"path": str(target), "bytes": target.stat().st_size, "sha256": _sha256(target),
            "source_url": source, "download_format": "gzip_stream_decompressed", "training_performed": False}

def load_pretrained_model(model_path: str | Path):
    """Load the official 300d Common Crawl FastText binary with subword/OOV support."""
    try:
        import fasttext
    except ImportError as exc:
        raise RuntimeError("Install pinned fasttext-new==0.1.0 and expose it through install_as_fasttext().") from exc
    path = Path(model_path)
    if not path.is_file(): raise FileNotFoundError(f"Pretrained FastText model not found: {path}")
    model = fasttext.load_model(str(path)); dimension = int(model.get_dimension())
    if dimension != 300: raise ValueError(f"Expected cc.en.300 (300d), got {dimension}d")
    return model

def prepare_pretrained_model(model_path: str | Path | None = None, cache_dir: str | Path | None = None, min_free_gb: float = 8.0):
    """Use a supplied model, a persistent external cache, or ephemeral download by default."""
    from tempfile import TemporaryDirectory
    if model_path is not None:
        path = Path(model_path)
        if not path.is_file(): raise FileNotFoundError(path)
        digest = _sha256(path); model = load_pretrained_model(path)
        return model, digest, {"path": str(path), "bytes": path.stat().st_size, "sha256": digest, "source": "user_supplied_local_file", "ephemeral": False, "training_performed": False}
    if cache_dir is not None:
        path = Path(cache_dir) / "cc.en.300.bin"
        if not path.is_file(): download_pretrained_model(path, min_free_gb=min_free_gb)
        digest = _sha256(path); model = load_pretrained_model(path)
        return model, digest, {"path": str(path), "bytes": path.stat().st_size, "sha256": digest, "source": DEFAULT_CONFIG["model_url"], "ephemeral": False, "training_performed": False}
    temporary = TemporaryDirectory(prefix='taas-e8-fasttext-'); path = Path(temporary.name) / 'cc.en.300.bin'
    try:
        meta = download_pretrained_model(path, min_free_gb=min_free_gb); model = load_pretrained_model(path)
        details = {**meta, "source": DEFAULT_CONFIG["model_url"], "ephemeral": True, "deleted_after_load": True}
        path.unlink(missing_ok=True); temporary.cleanup()
        return model, meta["sha256"], details
    except Exception:
        temporary.cleanup(); raise

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def run_track(track: Any, model: Any, output_dir: str | Path,
              model_fingerprint: str,
              config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run one E8 track independently and preserve its primary/sensitivity qrels."""
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    dimension = int(cfg["dimension"])
    started = time.perf_counter()
    tool_vectors, idf, corpus_stats = encode_corpus(track.tools, model, dimension)
    query_vectors, query_stats = encode_queries(track.tasks, model, idf, dimension)
    encode_seconds = time.perf_counter() - started
    task_ids = [t.task_id for t in track.tasks]
    tool_ids = [d.tool_id for d in track.tools]
    fingerprint_payload = {
        "track": track.dataset_id, "task_ids": task_ids,
        "query_text_sha256": hashlib.sha256(json.dumps(
            [t.query for t in track.tasks], ensure_ascii=False).encode()).hexdigest(),
        "tool_ids": tool_ids,
        "tool_text_sha256": hashlib.sha256(json.dumps(
            [d.text for d in track.tools], ensure_ascii=False).encode()).hexdigest(),
        "model_fingerprint": model_fingerprint, "config": cfg,
    }
    fingerprint = hashlib.sha256(json.dumps(
        fingerprint_payload, sort_keys=True).encode()).hexdigest()
    retrieval_started = time.perf_counter()
    rankings = rank_embeddings_checkpointed(
        query_vectors, tool_vectors, tool_ids, task_ids,
        output / "checkpoints", fingerprint, int(cfg["top_k"]),
        int(cfg["checkpoint_tasks"]),
    )
    retrieval_seconds = time.perf_counter() - retrieval_started
    primary_metrics = ranking_metrics(rankings, track.qrels, ks=(1, 5, 10))
    secondary_metrics = (
        ranking_metrics(rankings, track.secondary_qrels, ks=(1, 5, 10))
        if getattr(track, "secondary_qrels", None) else None
    )
    result = {
        "experiment": "E8-CPU-StaticEmbedding-v2", "track": track.dataset_id,
        "status": "executed", "method": "pretrained_fasttext_cc_en_300_idf_weighted_mean_cosine",
        "config": cfg,
        "counts": {"tasks": len(track.tasks), "candidate_tools": len(track.tools),
                   "qrel_tasks": sum(bool(track.qrels.get(t.task_id)) for t in track.tasks),
                   "exclusions": track.exclusions},
        "corpus": corpus_stats, "queries": query_stats,
        "metrics_primary_qrels": primary_metrics,
        "metrics_secondary_sensitivity_qrels": secondary_metrics,
        "timing_seconds": {"encoding": encode_seconds, "retrieval": retrieval_seconds,
                           "retrieval_per_query": retrieval_seconds / max(1, len(track.tasks))},
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "cpu_count": os.cpu_count(),
                    "fasttext_package_version": _package_version("fasttext-new"),
                    "device": "cpu", "cpu_only": True},
        "model_sha256": model_fingerprint, "source_manifest": track.source_manifest,
    }
    (output / "rankings.json").write_text(json.dumps(
        rankings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(
        result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--raw-root', type=Path, default=Path('data/raw'))
    parser.add_argument('--toolret-dir', type=Path, default=Path('data/processed/toolret'))
    parser.add_argument('--output-root', type=Path, default=Path('results/E8-CPU-StaticEmbedding-v2'))
    parser.add_argument('--model-path', type=Path, default=None, help='Use an existing cc.en.300.bin')
    parser.add_argument('--model-cache-dir', type=Path, default=None, help='Persist model outside repository; default is ephemeral')
    parser.add_argument('--min-free-disk-gb', type=float, default=8.0)
    parser.add_argument('--top-k', type=int, default=10)
    args = parser.parse_args(); os.environ['CUDA_VISIBLE_DEVICES'] = ''
    root = args.root.resolve(); os.chdir(root)
    raw = args.raw_root if args.raw_root.is_absolute() else root / args.raw_root
    toolret = args.toolret_dir if args.toolret_dir.is_absolute() else root / args.toolret_dir
    output = args.output_root if args.output_root.is_absolute() else root / args.output_root
    cfg = dict(DEFAULT_CONFIG, top_k=args.top_k, min_free_disk_gb=args.min_free_disk_gb)
    tracks = [load_toolret_track(toolret), load_mcptoolbenchpp_track(raw)]
    model, model_hash, model_metadata = prepare_pretrained_model(args.model_path, args.model_cache_dir, args.min_free_disk_gb)
    for track in tracks:
        directory = output / track.dataset_id
        result = run_track(track, model, directory, model_hash, cfg)
        result['model'] = model_metadata
        (directory / 'metrics.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(json.dumps({'track': track.dataset_id, 'tasks': result['counts']['tasks'], 'candidate_tools': result['counts']['candidate_tools'],
                          'Hit@1': result['metrics_primary_qrels']['metrics']['1']['hit@1']['value'],
                          'Hit@5': result['metrics_primary_qrels']['metrics']['5']['hit@5']['value'],
                          'MRR@10': result['metrics_primary_qrels']['metrics']['10']['mrr@10']['value']}, indent=2))

if __name__ == "__main__":
    main()
