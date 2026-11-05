"""Protocol-controlled E8 single-tool retrieval campaign.

Runs independent retrieval tracks over:
  * ToolRet: heterogeneous tool-retrieval benchmark (full corpus + graded qrels).
  * MCPToolBench++: MCP-only single-target subset (87-tool repository snapshot).

Discovery receives only queries and candidate tool definitions. Evaluator references
are loaded and scored only after all rankings for a track have been materialized.
The runner never edits source datasets or previously written result directories.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import re
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

from taas.data.registries import load_mcptoolbenchpp
from taas.experiments.evaluation_metrics import ranking_metrics


REQUIRED_BASELINES = ("random", "bm25", "tfidf", "dense_lsa", "e5_dense", "bm25_e5_rrf", "cross_encoder")
K_VALUES = (1, 5, 10)
RRF_K0 = 60
CROSS_ENCODER_CANDIDATE_K = 100


@dataclass(frozen=True)
class DiscoveryTask:
    task_id: str
    query: str
    category: str


@dataclass(frozen=True)
class ToolDocument:
    tool_id: str
    text: str
    category: str
    server_id: str


@dataclass
class DatasetTrack:
    dataset_id: str
    tasks: list[DiscoveryTask]
    tools: list[ToolDocument]
    qrels: dict[str, dict[str, float]]
    cluster_by_task: dict[str, str]
    exclusions: dict[str, int]
    source_manifest: dict[str, Any]
    secondary_qrels: dict[str, dict[str, float]] = field(default_factory=dict)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _git_value(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", str(text).casefold())


def _stable_seed(seed: int, task_id: str) -> int:
    digest = hashlib.sha256(f"{seed}\0{task_id}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _validate_unique_ids(values: Sequence[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} contains duplicate IDs")


def load_toolret_track(processed_dir: str | Path) -> DatasetTrack:
    """Load the ToolRet discovery corpus and evaluator qrels from separate directories."""
    root = Path(processed_dir)
    required = [
        root / "manifest.json",
        root / "discovery" / "tools.json",
        root / "discovery" / "tasks.json",
        root / "evaluator" / "task_references.json",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Missing ToolRet adapter output: {path}")
    manifest = json.loads(required[0].read_text(encoding="utf-8"))
    tools_raw = json.loads(required[1].read_text(encoding="utf-8"))
    tasks_raw = json.loads(required[2].read_text(encoding="utf-8"))
    refs_raw = json.loads(required[3].read_text(encoding="utf-8"))

    tools: list[ToolDocument] = []
    for row in tools_raw:
        if any(key in row for key in ("labels", "relevance", "qrels", "target_tool_ids")):
            raise ValueError("ToolRet discovery tools contain evaluator-only fields")
        tool_id = str(row.get("tool_id") or "")
        if not tool_id:
            raise ValueError("ToolRet discovery tool lacks tool_id")
        text = " ".join([
            str(row.get("name") or ""),
            str(row.get("description") or ""),
            json.dumps(row.get("input_schema") or {}, ensure_ascii=False, sort_keys=True),
        ]).strip()
        tools.append(ToolDocument(tool_id, text, str(row.get("category") or "all"),
                                  str(row.get("server_id") or "toolret_source_local")))

    tasks: list[DiscoveryTask] = []
    for row in tasks_raw:
        if any(key in row for key in ("labels", "relevance_judgments", "target_tool_ids", "answer")):
            raise ValueError("ToolRet discovery tasks contain evaluator-only fields")
        task_id = str(row.get("task_id") or "")
        query = str(row.get("prompt") or "").strip()
        if not task_id or not query:
            raise ValueError("ToolRet discovery task requires task_id and prompt")
        tasks.append(DiscoveryTask(task_id, query, str(row.get("category") or "all")))

    _validate_unique_ids([t.tool_id for t in tools], "ToolRet corpus")
    _validate_unique_ids([t.task_id for t in tasks], "ToolRet task set")
    task_ids = {t.task_id for t in tasks}
    tool_ids = {t.tool_id for t in tools}

    qrels: dict[str, dict[str, float]] = {}
    for row in refs_raw:
        task_id = str(row.get("task_id") or "")
        if task_id not in task_ids:
            raise ValueError(f"ToolRet evaluator qrels refer to unknown task {task_id}")
        labels = row.get("relevance_judgments") or []
        judgment: dict[str, float] = {}
        for label in labels:
            tool_id = str(label.get("tool_id") or "")
            if tool_id not in tool_ids:
                raise ValueError(f"ToolRet qrels refer to a tool outside the full corpus: {tool_id}")
            judgment[tool_id] = float(label.get("relevance", 1))
        qrels[task_id] = judgment

    # No query split is inferred. Cluster bootstrap is not justified by synthetic
    # "server" IDs in this heterogeneous corpus; use task-level paired inference.
    exclusions = {
        "tasks_total": len(tasks),
        "tasks_with_qrels": sum(bool(qrels.get(t.task_id)) for t in tasks),
        "tasks_without_qrels": sum(not bool(qrels.get(t.task_id)) for t in tasks),
        "qrel_rows": len(refs_raw),
    }
    return DatasetTrack(
        "toolret_heterogeneous", tasks, tools, qrels, {},
        exclusions,
        {
            "adapter_manifest_sha256": _sha256_file(required[0]),
            "tools_sha256": _sha256_file(required[1]),
            "tasks_sha256": _sha256_file(required[2]),
            "evaluator_qrels_sha256": _sha256_file(required[3]),
            "source_manifest": manifest,
        },
    )


def load_mcptoolbenchpp_track(raw_root: str | Path) -> DatasetTrack:
    """Load only single-primary-target tasks; retain similar_tools as sensitivity qrels."""
    raw_root = Path(raw_root)
    tools_raw, tasks_raw = load_mcptoolbenchpp(raw_root)
    tools_by_id = {tool.id: tool for tool in tools_raw}
    docs = [
        ToolDocument(
            tool.id,
            " ".join([
                tool.name, tool.server, tool.category, tool.description,
                json.dumps(tool.input_schema or {}, ensure_ascii=False, sort_keys=True),
            ]).strip(),
            tool.category or "unspecified",
            tool.server,
        )
        for tool in tools_raw
    ]

    # Read raw annotations because the shared registry loader intentionally stores
    # only the primary function_call_label and does not retain similar_tools.
    raw_task_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for source_file in sorted((raw_root / "mcptoolbenchpp").glob("*.json")):
        category = source_file.stem
        for row in json.loads(source_file.read_text(encoding="utf-8")):
            raw_task_rows[(category, str(row.get("uuid") or ""))] = row

    task_rows: list[DiscoveryTask] = []
    qrels: dict[str, dict[str, float]] = {}
    secondary_qrels: dict[str, dict[str, float]] = {}
    clusters: dict[str, str] = {}
    exclusions = defaultdict(int)
    for task in tasks_raw:
        exclusions["tasks_total"] += 1
        if not task.query.strip():
            exclusions["empty_query"] += 1
            continue
        if len(task.gold_tools) != 1:
            exclusions["not_single_gold_tool"] += 1
            continue
        target = task.gold_tools[0]
        if "|" in target or target.startswith("unknown::") or target not in tools_by_id:
            exclusions["unresolved_or_ambiguous_gold"] += 1
            continue
        task_id = f"{task.category}::{task.id}"
        if task_id in qrels:
            raise ValueError(f"Duplicate MCPToolBench++ task ID after category qualification: {task_id}")
        task_rows.append(DiscoveryTask(task_id, task.query, task.category or "unspecified"))
        qrels[task_id] = {target: 1.0}
        clusters[task_id] = tools_by_id[target].server

        raw_row = raw_task_rows.get((task.category, task.id), {})
        labels = raw_row.get("function_call_label") or []
        primary_label = labels[0] if labels else {}
        similar = primary_label.get("similar_tools") or []
        accepted = {target: 1.0}
        server_by_name = {
            name: server
            for server, names in (raw_row.get("mcp_tools_dict") or {}).items()
            for name in names
        }
        for alternative in similar:
            name = str(alternative.get("name") or "").strip()
            if not name:
                exclusions["similar_tool_missing_name"] += 1
                continue
            server = str(alternative.get("mcp_server") or server_by_name.get(name) or "unknown")
            alternative_id = f"{server}::{name}"
            exclusions["similar_tools_total"] += 1
            if alternative_id in tools_by_id:
                accepted[alternative_id] = 1.0
                exclusions["similar_tools_resolved"] += 1
            else:
                exclusions["similar_tools_unresolved"] += 1
        secondary_qrels[task_id] = accepted

    exclusions["tasks_evaluated"] = len(task_rows)
    exclusions["tasks_excluded"] = exclusions["tasks_total"] - len(task_rows)
    exclusions["candidate_tools"] = len(docs)
    if not task_rows:
        raise ValueError("MCPToolBench++ yielded no unambiguous single-target tasks for E8")
    return DatasetTrack(
        "mcptoolbenchpp_single_target", task_rows, docs, qrels, clusters,
        dict(exclusions),
        {
            "raw_root": str(raw_root.resolve()),
            "source_revisions_file": str((raw_root / "SOURCES.txt").resolve()),
            "source_revisions_sha256": _sha256_file(raw_root / "SOURCES.txt"),
            "source_revisions": (raw_root / "SOURCES.txt").read_text(encoding="utf-8"),
            "selection_rule": "exactly one resolved primary function_call_label; ambiguous/multiple labels excluded",
            "primary_metric_semantics": "primary function_call_label only",
            "sensitivity_metric_semantics": "primary target plus source-annotated similar_tools that resolve into the candidate corpus",
        },
        secondary_qrels,
    )


def _rank_scores(scores: np.ndarray, ids: Sequence[str], top_k: int | None = None) -> list[str]:
    if top_k is None or top_k >= len(ids):
        order = sorted(range(len(ids)), key=lambda i: (-float(scores[i]), ids[i]))
    else:
        # Partition first, then break exact score ties by stable tool ID.
        boundary = np.partition(scores, len(scores) - top_k)[len(scores) - top_k]
        above = [i for i, value in enumerate(scores) if float(value) > float(boundary)]
        tied = [i for i, value in enumerate(scores) if float(value) == float(boundary)]
        above.sort(key=lambda i: (-float(scores[i]), ids[i]))
        tied.sort(key=lambda i: ids[i])
        order = above + tied[:max(0, top_k - len(above))]
        order.sort(key=lambda i: (-float(scores[i]), ids[i]))
    return [ids[i] for i in order[:top_k]] if top_k is not None else [ids[i] for i in order]


def _bm25_rankings(
    docs: Sequence[ToolDocument], tasks: Sequence[DiscoveryTask], top_k: int
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    try:
        from rank_bm25 import BM25Okapi
    except ImportError as exc:
        raise RuntimeError("Install the benchmark-hf extra to run BM25") from exc
    ids = [x.tool_id for x in docs]
    tokenized = [_tokenize(x.text) for x in docs]
    if not tokenized or not any(tokenized):
        raise ValueError("BM25 corpus contains no lexical tokens")
    model = BM25Okapi(tokenized)
    all_rankings, candidates = {}, {}
    candidate_k = min(len(ids), max(top_k, CROSS_ENCODER_CANDIDATE_K))
    for task in tasks:
        scores = np.asarray(model.get_scores(_tokenize(task.query)), dtype=float)
        ranked = _rank_scores(scores, ids, candidate_k)
        all_rankings[task.task_id] = ranked[:top_k]
        candidates[task.task_id] = ranked[:CROSS_ENCODER_CANDIDATE_K]
    return all_rankings, candidates


def _tfidf_rankings(
    docs: Sequence[ToolDocument], tasks: Sequence[DiscoveryTask], top_k: int
) -> dict[str, list[str]]:
    ids = [x.tool_id for x in docs]
    texts = [x.text for x in docs]
    vectorizer = TfidfVectorizer(
        tokenizer=_tokenize, preprocessor=None, token_pattern=None,
        lowercase=False, norm="l2", sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(texts)
    result = {}
    for task in tasks:
        query = vectorizer.transform([task.query])
        scores = (query @ matrix.T).toarray().ravel()
        result[task.task_id] = _rank_scores(scores, ids, top_k)
    return result


def _lsa_rankings(
    docs: Sequence[ToolDocument], tasks: Sequence[DiscoveryTask], top_k: int,
    dimension: int = 128, seed: int = 0,
) -> dict[str, list[str]]:
    """Explicit LSA surrogate (TF-IDF + truncated SVD), not a neural dense encoder."""
    ids = [x.tool_id for x in docs]
    vectorizer = TfidfVectorizer(
        tokenizer=_tokenize, preprocessor=None, token_pattern=None,
        lowercase=False, norm="l2", sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([x.text for x in docs])
    components = min(dimension, matrix.shape[0] - 1, matrix.shape[1] - 1)
    if components < 1:
        raise ValueError("LSA requires at least two documents and two vocabulary terms")
    svd = TruncatedSVD(n_components=components, random_state=seed, n_iter=7)
    tool_vectors = svd.fit_transform(matrix)
    tool_norms = np.linalg.norm(tool_vectors, axis=1, keepdims=True)
    tool_vectors = tool_vectors / np.maximum(tool_norms, 1e-12)
    query_vectors = svd.transform(vectorizer.transform([x.query for x in tasks]))
    query_norms = np.linalg.norm(query_vectors, axis=1, keepdims=True)
    query_vectors = query_vectors / np.maximum(query_norms, 1e-12)
    scores = query_vectors @ tool_vectors.T
    return {
        task.task_id: _rank_scores(np.asarray(scores[i], dtype=float), ids, top_k)
        for i, task in enumerate(tasks)
    }


def _load_sentence_models(
    e5_model: str, e5_revision: str, cross_model: str, cross_revision: str, device: str
):
    try:
        from sentence_transformers import SentenceTransformer, CrossEncoder
    except ImportError as exc:
        raise RuntimeError("Install sentence-transformers to run E5 and cross-encoder baselines") from exc
    encoder = SentenceTransformer(e5_model, revision=e5_revision, device=device)
    reranker = CrossEncoder(cross_model, revision=cross_revision, device=device)
    return encoder, reranker


def _dense_and_hybrid_rankings(
    docs: Sequence[ToolDocument], tasks: Sequence[DiscoveryTask], top_k: int,
    encoder: Any, bm25_candidates: Mapping[str, Sequence[str]],
    rrf_k0: int = RRF_K0,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    ids = [x.tool_id for x in docs]
    passages = ["passage: " + x.text for x in docs]
    queries = ["query: " + x.query for x in tasks]
    passage_vectors = encoder.encode(
        passages, batch_size=64, convert_to_numpy=True,
        normalize_embeddings=True, show_progress_bar=True,
    )
    query_vectors = encoder.encode(
        queries, batch_size=64, convert_to_numpy=True,
        normalize_embeddings=True, show_progress_bar=True,
    )
    dense_rankings, hybrid_rankings, dense_candidates = {}, {}, {}
    # Chunk query-document matrix multiplication to bound peak memory on Colab.
    query_chunk_size = 64
    for start in range(0, len(tasks), query_chunk_size):
        end = min(len(tasks), start + query_chunk_size)
        score_block = query_vectors[start:end] @ passage_vectors.T
        for offset, task in enumerate(tasks[start:end]):
            dense_order = _rank_scores(
                np.asarray(score_block[offset], dtype=float),
                ids,
                min(CROSS_ENCODER_CANDIDATE_K, len(ids)),
            )
            dense_candidates[task.task_id] = dense_order
            dense_rankings[task.task_id] = dense_order[:top_k]

    for task in tasks:
        fused = defaultdict(float)
        for rank, tool_id in enumerate(bm25_candidates[task.task_id], start=1):
            fused[tool_id] += 1.0 / (rrf_k0 + rank)
        for rank, tool_id in enumerate(dense_candidates[task.task_id], start=1):
            fused[tool_id] += 1.0 / (rrf_k0 + rank)
        hybrid_rankings[task.task_id] = sorted(
            fused, key=lambda tool_id: (-fused[tool_id], tool_id)
        )[:top_k]
    return dense_rankings, hybrid_rankings, dense_candidates


def _cross_encoder_rankings(
    docs: Sequence[ToolDocument],
    tasks: Sequence[DiscoveryTask],
    candidates: Mapping[str, Sequence[str]],
    reranker: Any,
    top_k: int,
) -> dict[str, list[str]]:
    doc_by_id = {x.tool_id: x.text for x in docs}
    result = {}
    task_chunk_size = 32
    for start in range(0, len(tasks), task_chunk_size):
        chunk = tasks[start:start + task_chunk_size]
        pairs = []
        bounds = []
        for task in chunk:
            candidate_ids = list(candidates[task.task_id])[:CROSS_ENCODER_CANDIDATE_K]
            left = len(pairs)
            pairs.extend((task.query, doc_by_id[tool_id]) for tool_id in candidate_ids)
            bounds.append((task.task_id, candidate_ids, left, len(pairs)))
        if not pairs:
            continue
        scores = np.asarray(
            reranker.predict(pairs, batch_size=64, show_progress_bar=False), dtype=float
        )
        for task_id, candidate_ids, left, right in bounds:
            result[task_id] = _rank_scores(scores[left:right], candidate_ids, top_k)
    return result


def _random_rankings(
    docs: Sequence[ToolDocument], tasks: Sequence[DiscoveryTask], top_k: int, seed: int
) -> dict[str, list[str]]:
    ids = [x.tool_id for x in docs]
    result = {}
    for task in tasks:
        order = list(ids)
        random.Random(_stable_seed(seed, task.task_id)).shuffle(order)
        result[task.task_id] = order[:top_k]
    return result


def _per_task_metric(
    rankings: Mapping[str, Sequence[str]],
    qrels: Mapping[str, Mapping[str, float]],
    metric: str,
    k: int,
) -> dict[str, float]:
    values = {}
    for task_id, rel in qrels.items():
        if not rel:
            continue
        one = ranking_metrics({task_id: rankings.get(task_id, [])}, {task_id: rel}, ks=(k,))
        values[task_id] = float(one["metrics"][str(k)][f"{metric}@{k}"]["value"])
    return values


def _paired_sign_flip_pvalue(
    left: Mapping[str, float], right: Mapping[str, float], clusters: Mapping[str, str] | None,
    seed: int = 20261105, permutations: int = 5000,
) -> dict[str, Any]:
    """Two-sided paired sign-flip test over tasks or independent server clusters."""
    ids = sorted(set(left) & set(right))
    if not ids:
        return {"p_value_two_sided": None, "n_tasks": 0, "n_independent_units": 0, "unit": "none"}
    differences = {key: float(left[key]) - float(right[key]) for key in ids}
    if clusters and all(task_id in clusters for task_id in ids):
        groups = defaultdict(list)
        for task_id, value in differences.items():
            groups[clusters[task_id]].append(value)
        samples = [sum(values) / len(values) for _, values in sorted(groups.items())]
        unit = "target_server_cluster"
    else:
        samples = [differences[key] for key in ids]
        unit = "task"
    observed = abs(sum(samples) / len(samples))
    n = len(samples)
    if n <= 18:
        exceed = 0
        total = 1 << n
        for mask in range(total):
            value = abs(sum((sample if (mask >> i) & 1 else -sample)
                            for i, sample in enumerate(samples)) / n)
            exceed += value >= observed - 1e-15
        p_value = exceed / total
        method = "exact sign flip"
    else:
        rng = np.random.default_rng(seed)
        exceed = 0
        total = permutations
        sample_array = np.asarray(samples, dtype=float)
        chunk_size = 256
        for offset in range(0, permutations, chunk_size):
            count = min(chunk_size, permutations - offset)
            signs = rng.choice(np.array([-1.0, 1.0]), size=(count, n))
            values = np.abs((signs * sample_array[None, :]).mean(axis=1))
            exceed += int(np.count_nonzero(values >= observed - 1e-15))
        p_value = (exceed + 1) / (total + 1)
        method = "Monte Carlo sign flip"
    return {
        "estimate_left_minus_right": sum(samples) / n,
        "p_value_two_sided": p_value,
        "n_tasks": len(ids),
        "n_independent_units": n,
        "unit": unit,
        "method": method,
        "permutations": total,
        "seed": seed,
    }


def _paired_bootstrap_ci(
    left: Mapping[str, float], right: Mapping[str, float],
    clusters: Mapping[str, str] | None, seed: int = 20261105,
    resamples: int = 5000,
) -> dict[str, Any]:
    """Paired percentile CI, resampling tasks or whole target-server clusters."""
    ids = sorted(set(left) & set(right))
    if not ids:
        return {"estimate": None, "lower": None, "upper": None, "n_tasks": 0}
    diffs = {task_id: float(left[task_id]) - float(right[task_id]) for task_id in ids}
    task_estimate = sum(diffs.values()) / len(diffs)
    if clusters and all(task_id in clusters for task_id in ids):
        groups = defaultdict(list)
        for task_id, value in diffs.items():
            groups[clusters[task_id]].append(value)
        units = [sum(values) / len(values) for _, values in sorted(groups.items())]
        unit_name = "target_server_cluster"
    else:
        units = [diffs[task_id] for task_id in ids]
        unit_name = "task"
    rng = np.random.default_rng(seed)
    unit_values = np.asarray(units, dtype=float)
    draws = np.empty(resamples, dtype=float)
    chunk_size = 256
    for offset in range(0, resamples, chunk_size):
        count = min(chunk_size, resamples - offset)
        indices = rng.integers(0, len(unit_values), size=(count, len(unit_values)))
        draws[offset:offset + count] = unit_values[indices].mean(axis=1)
    draws.sort()
    lo = int(0.025 * resamples)
    hi = min(resamples - 1, int(0.975 * resamples))
    return {
        "estimate_task_weighted": task_estimate,
        "lower": draws[lo],
        "upper": draws[hi],
        "n_tasks": len(ids),
        "n_independent_units": len(units),
        "resampling_unit": unit_name,
        "confidence": 0.95,
        "resamples": resamples,
        "seed": seed,
    }


def _holm_adjust(rows: list[dict[str, Any]]) -> None:
    eligible = [(i, row["p_value_raw"]) for i, row in enumerate(rows)
                if isinstance(row.get("p_value_raw"), (int, float))]
    ordered = sorted(eligible, key=lambda pair: pair[1])
    m = len(ordered)
    adjusted = [0.0] * len(ordered)
    running = 0.0
    for rank, (_, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * float(p_value)))
        adjusted[rank] = running
    for (index, _), value in zip(ordered, adjusted):
        rows[index]["p_value_holm"] = value


def _macro_hit1_by_category(
    track: DatasetTrack, rankings: Mapping[str, Sequence[str]]
) -> dict[str, dict[str, float | int | None]]:
    groups = defaultdict(list)
    for task in track.tasks:
        groups[task.category].append(task.task_id)
    output = {}
    for category, ids in sorted(groups.items()):
        valid = [task_id for task_id in ids if track.qrels.get(task_id)]
        if not valid:
            continue
        hits = [
            float(any(tool in track.qrels[task_id] and track.qrels[task_id][tool] > 0
                      for tool in rankings.get(task_id, [])[:1]))
            for task_id in valid
        ]
        output[category] = {"hit@1": sum(hits) / len(hits), "n": len(hits)}
    return output


def _plot_track(track_id: str, metrics: dict[str, Any], output_dir: Path) -> list[str]:
    baseline_ids = list(metrics)
    paths = []
    for metric_name in ("hit@1", "hit@5", "mrr@10", "ndcg@10"):
        fig, ax = plt.subplots(figsize=(9, 4.8))
        labels, values = [], []
        for baseline in baseline_ids:
            entry = metrics[baseline]["metrics"]["overall"]["metrics"]["10" if metric_name.endswith("@10") else metric_name.split("@")[1]]
            value = entry[metric_name]["value"]
            if value is not None:
                labels.append(baseline)
                values.append(value)
        ax.bar(labels, values)
        ax.set_title(f"{track_id} — {metric_name}")
        ax.set_ylabel(metric_name)
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylim(0, 1)
        fig.tight_layout()
        filename = f"{track_id}_{metric_name.replace('@', '_')}.png"
        fig.savefig(output_dir / filename, dpi=160)
        plt.close(fig)
        paths.append(filename)
    return paths


def evaluate_track(
    track: DatasetTrack,
    rankings: dict[str, dict[str, list[str]]],
    candidate_sets: dict[str, dict[str, list[str]]],
    output_dir: Path,
) -> dict[str, Any]:
    """Evaluator-only stage; called after discovery rankings have all been frozen."""
    metrics: dict[str, Any] = {}
    for baseline, per_task in rankings.items():
        overall = ranking_metrics(per_task, track.qrels, ks=K_VALUES)
        metrics[baseline] = {
            "metrics": {"overall": overall},
            "macro_hit1_by_category": _macro_hit1_by_category(track, per_task),
            "macro_hit@1": {
                "value": (
                    sum(x["hit@1"] for x in _macro_hit1_by_category(track, per_task).values())
                    / len(_macro_hit1_by_category(track, per_task))
                    if _macro_hit1_by_category(track, per_task) else None
                ),
                "n_categories": len(_macro_hit1_by_category(track, per_task)),
            },
        }

    paired = []
    if "bm25" in rankings:
        for competitor in ("tfidf", "dense_lsa", "random", "e5_dense", "bm25_e5_rrf", "cross_encoder"):
            if competitor not in rankings:
                continue
            for metric, k in (("hit", 1), ("hit", 5), ("mrr", 10), ("ndcg", 10)):
                left = _per_task_metric(rankings[competitor], track.qrels, metric, k)
                right = _per_task_metric(rankings["bm25"], track.qrels, metric, k)
                test = _paired_sign_flip_pvalue(left, right, track.cluster_by_task)
                ci = _paired_bootstrap_ci(left, right, track.cluster_by_task)
                paired.append({
                    "track": track.dataset_id, "contrast": f"{competitor}_minus_bm25",
                    "metric": f"{metric}@{k}", "p_value_raw": test.get("p_value_two_sided"),
                    "paired_bootstrap_ci": ci,
                    **test,
                })
        _holm_adjust(paired)

    candidate_recall = {}
    if "cross_encoder" in rankings and candidate_sets:
        values = []
        for task_id, rel in track.qrels.items():
            relevant = {key for key, grade in rel.items() if float(grade) > 0}
            if not relevant:
                continue
            pool = set(candidate_sets.get("bm25", {}).get(task_id, []))
            values.append(len(relevant & pool) / len(relevant))
        candidate_recall = {
            "candidate_k": CROSS_ENCODER_CANDIDATE_K,
            "mean_recall": sum(values) / len(values) if values else None,
            "n_tasks": len(values),
        }

    (output_dir / f"{track.dataset_id}_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / f"{track.dataset_id}_paired_tests.json").write_text(
        json.dumps(paired, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / f"{track.dataset_id}_exclusions.json").write_text(
        json.dumps(track.exclusions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if candidate_recall:
        (output_dir / f"{track.dataset_id}_cross_encoder_candidate_recall.json").write_text(
            json.dumps(candidate_recall, indent=2) + "\n", encoding="utf-8"
        )
    return {
        "metrics": metrics,
        "paired_tests": paired,
        "candidate_recall_at_100": candidate_recall,
    }


def _write_rankings(
    track_id: str, rankings: Mapping[str, Mapping[str, Sequence[str]]], output_dir: Path
) -> None:
    for baseline, values in rankings.items():
        path = output_dir / f"{track_id}_{baseline}_rankings.json"
        path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _json_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return _sha256_text(encoded)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _ranking_cache_key(
    track: DatasetTrack, baseline: str, models: Mapping[str, Any], top_k: int, seed: int
) -> str:
    return _json_fingerprint({
        "track_id": track.dataset_id,
        "source": track.source_manifest,
        "tools": [(item.tool_id, item.text, item.category, item.server_id) for item in track.tools],
        "tasks": [(item.task_id, item.query, item.category) for item in track.tasks],
        "baseline": baseline,
        "models": dict(models),
        "top_k": top_k,
        "seed": seed,
        "rrf_k0": RRF_K0,
        "cross_encoder_candidate_k": CROSS_ENCODER_CANDIDATE_K,
    })


def _load_ranking_cache(
    path: Path, meta_path: Path, cache_key: str,
    task_ids: set[str], tool_ids: set[str], max_length: int,
) -> dict[str, list[str]] | None:
    if not path.is_file() or not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("cache_key") != cache_key:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != task_ids:
        raise ValueError(f"Ranking cache task coverage mismatch: {path}")
    for task_id, ranked in data.items():
        if not isinstance(ranked, list) or len(ranked) > max_length:
            raise ValueError(f"Invalid ranking cache entry for {task_id}: {path}")
        if len(ranked) != len(set(ranked)) or any(tool_id not in tool_ids for tool_id in ranked):
            raise ValueError(f"Ranking cache contains duplicate/unknown candidate IDs: {path}")
    return {key: list(value) for key, value in data.items()}


def _save_ranking_cache(
    path: Path, meta_path: Path, rankings: Mapping[str, Sequence[str]],
    cache_key: str, baseline: str,
) -> None:
    _atomic_json(path, {key: list(value) for key, value in rankings.items()})
    _atomic_json(meta_path, {
        "cache_key": cache_key,
        "baseline": baseline,
        "task_count": len(rankings),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    })


def _write_per_task_csv(
    track: DatasetTrack, rankings: Mapping[str, Mapping[str, Sequence[str]]], output_dir: Path
) -> None:
    path = output_dir / f"{track.dataset_id}_per_task_metrics.csv"
    fields = ["baseline", "task_id", "category", "metric", "k", "value"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for baseline, ranking in rankings.items():
            for metric, k in (("precision", 1), ("recall", 1), ("mrr", 10),
                              ("ndcg", 10), ("hit", 1), ("hit", 5), ("ndcg", 10)):
                values = _per_task_metric(ranking, track.qrels, metric, k)
                category_by_id = {task.task_id: task.category for task in track.tasks}
                for task_id, value in values.items():
                    writer.writerow({
                        "baseline": baseline, "task_id": task_id,
                        "category": category_by_id.get(task_id, "unknown"),
                        "metric": metric, "k": k, "value": value,
                    })


def _file_inventory(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in {"FILE_HASHES.json", "MANIFEST.json"}:
            files[str(path.relative_to(root))] = _sha256_file(path)
    return files


def run_campaign(
    root: str | Path,
    output_root: str | Path,
    toolret_dir: str | Path,
    raw_root: str | Path,
    e5_model: str,
    e5_revision: str,
    cross_model: str,
    cross_revision: str,
    device: str = "cpu",
    top_k: int = 10,
    seed: int = 20261105,
    run_id: str | None = None,
) -> Path:
    root = Path(root).resolve()
    output_root = Path(output_root).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    requested_run_id = run_id is not None
    run_id = run_id or f"E8-{stamp}-{_sha256_text(str(seed) + stamp)[:8]}"
    run_dir = output_root / run_id
    if (run_dir / "MANIFEST.json").is_file():
        raise FileExistsError(f"Run {run_id} is immutable and already finalized")
    run_dir.mkdir(parents=True, exist_ok=requested_run_id)

    toolret = load_toolret_track(toolret_dir)
    mcp = load_mcptoolbenchpp_track(raw_root)
    models = {
        "e5_dense_model": e5_model,
        "e5_dense_revision": e5_revision,
        "cross_encoder_model": cross_model,
        "cross_encoder_revision": cross_revision,
        "device": device,
    }
    track_runs: dict[str, Any] = {}
    all_tracks = [toolret, mcp]
    track_fingerprints = {
        track.dataset_id: _json_fingerprint({
            "source": track.source_manifest,
            "tools": [(x.tool_id, x.text, x.category, x.server_id) for x in track.tools],
            "tasks": [(x.task_id, x.query, x.category) for x in track.tasks],
        })
        for track in all_tracks
    }
    run_context = {
        "runner_commit": _git_value(root, "rev-parse", "HEAD"),
        "models": models,
        "track_fingerprints": track_fingerprints,
        "top_k": top_k,
        "seed": seed,
    }
    run_context_key = _json_fingerprint(run_context)
    state_path = run_dir / "RUN_STATE.json"
    if state_path.exists():
        existing_state = json.loads(state_path.read_text(encoding="utf-8"))
        if existing_state.get("run_context_key") != run_context_key:
            raise ValueError(
                "Cannot resume this run ID: source snapshots, model revisions, top_k or seed changed. "
                "Use a new --run-id for a new experimental configuration."
            )
    else:
        _atomic_json(state_path, {
            "run_id": run_id,
            "run_context_key": run_context_key,
            "run_context": run_context,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        })

    encoder, reranker = _load_sentence_models(
        e5_model, e5_revision, cross_model, cross_revision, device
    )

    for track in all_tracks:
        start = time.perf_counter()
        docs, tasks = track.tools, track.tasks
        task_ids = {task.task_id for task in tasks}
        tool_ids = {tool.tool_id for tool in docs}
        rankings: dict[str, dict[str, list[str]]] = {}
        candidate_sets: dict[str, dict[str, list[str]]] = {}
        cache_hits = []
        cache_key = lambda baseline: _ranking_cache_key(track, baseline, models, top_k, seed)

        # Random ranking cache.
        random_path = run_dir / f"{track.dataset_id}_random_rankings.json"
        random_meta = run_dir / f"{track.dataset_id}_random_cache.json"
        cached = _load_ranking_cache(random_path, random_meta, cache_key("random"),
                                     task_ids, tool_ids, top_k)
        if cached is None:
            cached = _random_rankings(docs, tasks, top_k, seed)
            _save_ranking_cache(random_path, random_meta, cached, cache_key("random"), "random")
        else:
            cache_hits.append("random")
        rankings["random"] = cached

        # BM25 top-k and top-100 candidate set share one cached computation.
        bm25_key = cache_key("bm25")
        bm25_path = run_dir / f"{track.dataset_id}_bm25_rankings.json"
        bm25_meta = run_dir / f"{track.dataset_id}_bm25_cache.json"
        candidate_path = run_dir / f"{track.dataset_id}_bm25_candidates.json"
        candidate_meta = run_dir / f"{track.dataset_id}_bm25_candidates_cache.json"
        bm25_cached = _load_ranking_cache(
            bm25_path, bm25_meta, bm25_key, task_ids, tool_ids, top_k
        )
        candidate_cached = _load_ranking_cache(
            candidate_path, candidate_meta, _ranking_cache_key(
                track, "bm25_candidates", models, top_k, seed
            ), task_ids, tool_ids, CROSS_ENCODER_CANDIDATE_K
        )
        if bm25_cached is None or candidate_cached is None:
            bm25_cached, candidate_cached = _bm25_rankings(docs, tasks, top_k)
            _save_ranking_cache(bm25_path, bm25_meta, bm25_cached, bm25_key, "bm25")
            _save_ranking_cache(
                candidate_path, candidate_meta, candidate_cached,
                _ranking_cache_key(track, "bm25_candidates", models, top_k, seed),
                "bm25_candidates",
            )
        else:
            cache_hits.append("bm25")
        rankings["bm25"] = bm25_cached
        candidate_sets["bm25"] = candidate_cached

        # TF-IDF cache.
        tfidf_path = run_dir / f"{track.dataset_id}_tfidf_rankings.json"
        tfidf_meta = run_dir / f"{track.dataset_id}_tfidf_cache.json"
        cached = _load_ranking_cache(tfidf_path, tfidf_meta, cache_key("tfidf"),
                                     task_ids, tool_ids, top_k)
        if cached is None:
            cached = _tfidf_rankings(docs, tasks, top_k)
            _save_ranking_cache(tfidf_path, tfidf_meta, cached, cache_key("tfidf"), "tfidf")
        else:
            cache_hits.append("tfidf")
        rankings["tfidf"] = cached

        # LSA is retained as the explicitly labelled non-neural dense surrogate.
        lsa_path = run_dir / f"{track.dataset_id}_dense_lsa_rankings.json"
        lsa_meta = run_dir / f"{track.dataset_id}_dense_lsa_cache.json"
        cached = _load_ranking_cache(lsa_path, lsa_meta, cache_key("dense_lsa"),
                                     task_ids, tool_ids, top_k)
        if cached is None:
            cached = _lsa_rankings(docs, tasks, top_k, dimension=128, seed=0)
            _save_ranking_cache(lsa_path, lsa_meta, cached, cache_key("dense_lsa"), "dense_lsa")
        else:
            cache_hits.append("dense_lsa")
        rankings["dense_lsa"] = cached

        # E5 and truncated-union RRF are computed together and cached separately.
        dense_path = run_dir / f"{track.dataset_id}_e5_dense_rankings.json"
        dense_meta = run_dir / f"{track.dataset_id}_e5_dense_cache.json"
        hybrid_path = run_dir / f"{track.dataset_id}_bm25_e5_rrf_rankings.json"
        hybrid_meta = run_dir / f"{track.dataset_id}_bm25_e5_rrf_cache.json"
        dense_cached = _load_ranking_cache(dense_path, dense_meta, cache_key("e5_dense"),
                                           task_ids, tool_ids, top_k)
        hybrid_cached = _load_ranking_cache(hybrid_path, hybrid_meta, cache_key("bm25_e5_rrf"),
                                            task_ids, tool_ids, top_k)
        if dense_cached is None or hybrid_cached is None:
            dense_cached, hybrid_cached, _ = _dense_and_hybrid_rankings(
                docs, tasks, top_k, encoder, candidate_sets["bm25"]
            )
            _save_ranking_cache(dense_path, dense_meta, dense_cached, cache_key("e5_dense"), "e5_dense")
            _save_ranking_cache(
                hybrid_path, hybrid_meta, hybrid_cached, cache_key("bm25_e5_rrf"), "bm25_e5_rrf"
            )
        else:
            cache_hits.extend(["e5_dense", "bm25_e5_rrf"])
        rankings["e5_dense"] = dense_cached
        rankings["bm25_e5_rrf"] = hybrid_cached

        # Cross-encoder is evaluated on the fixed BM25 top-100 candidate pool.
        cross_path = run_dir / f"{track.dataset_id}_cross_encoder_rankings.json"
        cross_meta = run_dir / f"{track.dataset_id}_cross_encoder_cache.json"
        cached = _load_ranking_cache(cross_path, cross_meta, cache_key("cross_encoder"),
                                     task_ids, tool_ids, top_k)
        if cached is None:
            cached = _cross_encoder_rankings(
                docs, tasks, candidate_sets["bm25"], reranker, top_k
            )
            _save_ranking_cache(
                cross_path, cross_meta, cached, cache_key("cross_encoder"), "cross_encoder"
            )
        else:
            cache_hits.append("cross_encoder")
        rankings["cross_encoder"] = cached

        # Rankings are fully materialized before evaluator qrels are accessed.
        _write_rankings(track.dataset_id, rankings, run_dir)
        result = evaluate_track(track, rankings, candidate_sets, run_dir)
        _write_per_task_csv(track, rankings, run_dir)
        plots = _plot_track(track.dataset_id, result["metrics"], run_dir)
        track_runs[track.dataset_id] = {
            "task_count_discovery": len(tasks),
            "tool_count_candidates": len(docs),
            "exclusions": track.exclusions,
            "source": track.source_manifest,
            "baseline_status": {baseline: "EXECUTED" for baseline in rankings},
            "baseline_ids_executed": list(rankings),
            "baseline_fidelity": {
                "bm25": "native lexical baseline",
                "tfidf": "native lexical baseline",
                "random": "deterministic sanity baseline",
                "dense_lsa": "surrogate: TF-IDF plus truncated SVD",
                "e5_dense": "pinned neural dense encoder",
                "bm25_e5_rrf": "adaptation: reciprocal-rank fusion over BM25/E5 top-100 candidates",
                "cross_encoder": "reranker adaptation over BM25 top-100 candidates",
            },
            "cache_hits": cache_hits,
            "cache_misses": [baseline for baseline in rankings if baseline not in cache_hits],
            "plots": plots,
            "metrics_file": f"{track.dataset_id}_metrics.json",
            "paired_tests_file": f"{track.dataset_id}_paired_tests.json",
            "elapsed_seconds": time.perf_counter() - start,
            "candidate_recall_at_100": result["candidate_recall_at_100"],
        }

    # B1/B1m and planning/agent adapters are not silently replaced by other corpora.
    blocked = {
        "B1": {"status": "BLOCKED_DATA", "reason": "No B1 source data/split is present in the tracked repository tree."},
        "B1m": {"status": "BLOCKED_DATA", "reason": "No B1m source data/split is present in the tracked repository tree."},
        "mcp_atlas_public": {"status": "BLOCKED_DIAGNOSTIC_MAPPING", "reason": "Trajectory-to-enabled-tool identity resolution and a coverage-only diagnostic must be frozen before scoring; trajectories are not exhaustive gold sets."},
        "rag_mcp": {"status": "NOT_RUN_AS_DISTINCT_METHOD", "reason": "E5 global dense retrieval is reported separately; the registered RAG-MCP adaptation requires its own frozen method/configuration and must not be relabelled as E5."},
        "mcp_zero": {"status": "BLOCKED_ADAPTATION_INPUTS", "reason": "E8's single-tool requests do not include frozen GoalSpecs or the official active-request loop."},
        "per_subtask": {"status": "BLOCKED_ADAPTATION_INPUTS", "reason": "Requires frozen goal decompositions; not inferred from evaluator qrels."},
        "colt_adapted": {"status": "BLOCKED_TRAIN_SPLIT", "reason": "No declared ToolRet/MCPToolBench++ train/test task-tool bundle split is supplied to E8."},
        "toolscope_adapted": {"status": "NOT_COMPARABLE_IN_CURRENT_TRACK", "reason": "Its merge/identity metrics require an independent equivalence oracle; do not conflate cluster representatives with single-tool ranking."},
        "cmtf_adapted": {"status": "BLOCKED_CONTRACT_ORACLE", "reason": "Requires independent typed precondition/effect contracts not available in E8."},
    }
    manifest = {
        "schema_version": "1.0.0",
        "experiment_id": "E8",
        "title": "Single-tool retrieval quality",
        "run_id": run_id,
        "status": "partial",
        "execution_scope_status": "EXECUTED_SELECTED_RETRIEVAL_BASELINES",
        "completion_gate": "E8 remains partial until all preregistered baselines and B1/B1m data are available or formally ruled out.",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "branch": _git_value(root, "branch", "--show-current"),
            "commit": _git_value(root, "rev-parse", "HEAD"),
            "dirty_worktree": bool(_git_value(root, "status", "--porcelain")),
        },
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__},
        "protocol": {
            "candidate_pool": "complete source-specific corpus for each separate dataset track",
            "ranking_cutoffs": list(K_VALUES),
            "baseline_suite_executed": list(REQUIRED_BASELINES),
            "primary_metrics": ["Hit@1", "Hit@5", "MRR@10", "macro Hit@1"],
            "secondary_metrics": ["Precision@k", "Recall@k", "nDCG@k", "paired task/server sign-flip tests"],
            "multiple_testing": "Holm adjustment over the declared pairwise baseline-metric family within each track",
            "random_seed": seed,
            "cross_encoder_candidate_generation": f"BM25 top-{CROSS_ENCODER_CANDIDATE_K}, rerank then return top-{top_k}",
            "data_separation": "discovery queries/tools supplied to rankers; evaluator qrels consumed only after ranking JSON files are materialized",
            "tracks_are_not_pooled": True,
        },
        "models": models,
        "tracks": track_runs,
        "blocked_or_not_comparable": blocked,
        "protocol_baseline_status": {
            "preregistered_catalog_ids": ["bm25", "dense_lsa", "rag_mcp", "mcp_zero", "per_subtask", "colt_adapted", "toolscope_adapted", "cmtf_adapted"],
            "executed_retrieval_controls": list(REQUIRED_BASELINES),
            "blocked_or_not_comparable": sorted(blocked),
        },
        "scientific_limitations": [
            "ToolRet is a heterogeneous tool-retrieval track and is not pooled with MCP-only metrics.",
            "MCPToolBench++ includes only tasks with exactly one resolved gold tool; multi-tool, ambiguous and unresolved examples are counted as exclusions.",
            "B1/B1m were not found in the tracked data tree and are not substituted.",
            "E5 is a dense retrieval model; the BM25+E5 method uses reciprocal-rank fusion, not a tuned learned fusion.",
            "Cross-encoder results are conditional on BM25 top-100 candidate recall; the candidate ceiling is reported separately.",
            "COLT-style adaptation requires a true train split and training scenes; this run does not construct scenes from evaluation labels.",
            "MCP-Zero, per-subtask, ToolScope and CMTF are not falsely reported as executed in this retrieval-only run.",
            "No tool execution, observed effects, security oracle or task-success claims are evaluated by E8.",
            "The historical ToolRet BM25/TF-IDF/Random aggregate is a previous execution and is not silently pooled with this new run.",
            "This execution covers the lexical, dense E5, RRF hybrid and cross-encoder retrieval controls; registered planning/composition adaptations remain blocked as recorded above.",
        ],
    }
    (run_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "FILE_HASHES.json").write_text(
        json.dumps(_file_inventory(run_dir), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    archive = output_root / f"{run_id}.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(run_dir))
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-root", default="results/definitive/E8")
    parser.add_argument("--toolret-dir", default="data/processed/toolret")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--e5-model", default="intfloat/e5-small-v2")
    parser.add_argument("--e5-revision", required=True)
    parser.add_argument("--cross-encoder-model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--cross-encoder-revision", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261105)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.top_k < 10:
        raise SystemExit("--top-k must be >= 10 to cover E8's MRR@10")
    run_dir = run_campaign(
        args.root, args.output_root, args.toolret_dir, args.raw_root,
        args.e5_model, args.e5_revision, args.cross_encoder_model,
        args.cross_encoder_revision, args.device, args.top_k, args.seed, args.run_id,
    )
    print(json.dumps({
        "status": json.loads((run_dir / "MANIFEST.json").read_text())["status"],
        "run_dir": str(run_dir),
        "manifest": str(run_dir / "MANIFEST.json"),
        "archive": str(run_dir.parent / f"{run_dir.name}.zip"),
    }, indent=2))


if __name__ == "__main__":
    main()
