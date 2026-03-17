from __future__ import annotations

import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np

from agent_types import SearchOptions
from build_indexes import tokenize
from embed_chunks import embed_texts
from models import ChunkRecord, SearchHit
from settings import DEFAULT_ALPHA, DEFAULT_TOP_K, PATHS

try:
    import faiss
except Exception:  # pragma: no cover - optional at import time
    faiss = None


def _load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def _normalize(scores: np.ndarray) -> np.ndarray:
    if scores.size == 0:
        return scores
    minimum = scores.min()
    maximum = scores.max()
    if float(maximum - minimum) < 1e-9:
        return np.ones_like(scores) if maximum > 0 else np.zeros_like(scores)
    return (scores - minimum) / (maximum - minimum)


def _load_faiss_scores(query_embedding: np.ndarray, total_chunks: int, candidate_pool: int) -> dict[int, float]:
    if faiss is None or not PATHS.faiss_index_path.exists():
        return {}
    index = faiss.read_index(str(PATHS.faiss_index_path))
    search_k = min(max(candidate_pool * 8, 128), total_chunks)
    scores, ids = index.search(query_embedding.reshape(1, -1).astype(np.float32), search_k)
    mapping: dict[int, float] = {}
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        mapping[int(idx)] = float(score)
    return mapping


def _query_backend(vector_data: dict) -> str | None:
    backend_id = str(vector_data.get("backend_id", "")).lower()
    if backend_id:
        return backend_id
    model_name = str(vector_data.get("model_name", "")).lower()
    if model_name == "hashing-char-ngram":
        return "hashing"
    if model_name:
        return "sentence-transformers"
    return None


def _match_filters(chunk: ChunkRecord, filters: dict | None) -> bool:
    if not filters:
        return True
    for key, value in filters.items():
        if value is None:
            continue
        if key == "source" and chunk.source != value:
            return False
        if key == "series" and chunk.series != value:
            return False
        if key == "primary_category" and chunk.primary_category != value:
            return False
        if key == "topic_tags" and value not in chunk.topic_tags:
            return False
        if key == "attribute_tags" and value not in chunk.attribute_tags:
            return False
    return True


def _count_active_filters(filters: dict[str, str | None] | None) -> int:
    if not filters:
        return 0
    return sum(1 for value in filters.values() if value is not None)


def _heading_bonus(query_tokens: list[str], chunk: ChunkRecord) -> float:
    if not query_tokens:
        return 0.0
    heading_text = f"{chunk.doc_title} {chunk.section_title}".lower()
    token_hits = sum(1 for token in set(query_tokens) if token and token in heading_text)
    if token_hits == 0:
        return 0.0
    return min(0.12, 0.04 * token_hits)


def _intent_bonus(query_tokens: list[str], chunk: ChunkRecord) -> float:
    joined_query = "".join(query_tokens)
    text = f"{chunk.section_title} {chunk.text}".lower()
    bonus = 0.0
    if any(marker in joined_query for marker in ["本质", "核心", "根本", "真正原因"]):
        if any(token in text for token in ["本质", "根本", "核心", "真正", "更深", "深层"]):
            bonus += 0.12
    if any(marker in joined_query for marker in ["为什么", "原因"]):
        if any(token in text for token in ["因为", "原因", "导致", "所以", "背后"]):
            bonus += 0.08
    if any(marker in joined_query for marker in ["怎么", "如何"]):
        if any(token in text for token in ["方法", "步骤", "应该", "可以", "做法"]):
            bonus += 0.08
    return min(bonus, 0.14)


def _content_penalty(chunk: ChunkRecord) -> float:
    if chunk.char_count < 180:
        return -0.08
    if chunk.char_count < 260:
        return -0.04
    return 0.0


def _boost_for_filters(filters: dict[str, str | None] | None) -> float:
    active_count = _count_active_filters(filters)
    return min(0.08, active_count * 0.02)


def _candidate_hit(
    chunk: ChunkRecord,
    bm25_score: float,
    vector_score: float,
    raw_bm25_score: float,
    raw_vector_score: float,
    query_tokens: list[str],
    filters: dict[str, str | None] | None,
) -> SearchHit:
    score = 0.55 * vector_score + 0.45 * bm25_score
    score += _heading_bonus(query_tokens, chunk)
    score += _intent_bonus(query_tokens, chunk)
    score += _boost_for_filters(filters)
    score += _content_penalty(chunk)
    score = max(score, 0.0)
    return SearchHit(
        chunk_id=chunk.chunk_id,
        score=float(score),
        bm25_score=float(bm25_score),
        vector_score=float(vector_score),
        chunk=chunk,
        raw_bm25_score=float(raw_bm25_score),
        raw_vector_score=float(raw_vector_score),
    )


def _dedupe_hits(hits: list[SearchHit], limit: int) -> list[SearchHit]:
    deduped: list[SearchHit] = []
    seen_sections: set[tuple[str, str]] = set()
    for hit in hits:
        key = (hit.chunk.doc_id, hit.chunk.section_title)
        if key in seen_sections:
            continue
        deduped.append(hit)
        seen_sections.add(key)
        if len(deduped) >= limit:
            break
    return deduped


def _expand_neighbor_hits(
    selected_hits: list[SearchHit],
    chunks: list[ChunkRecord],
    max_context_chunks: int,
    max_context_chars: int,
) -> list[SearchHit]:
    chunk_lookup = {chunk.chunk_id: chunk for chunk in chunks}
    by_section: dict[tuple[str, str], dict[int, ChunkRecord]] = defaultdict(dict)
    for chunk in chunks:
        by_section[(chunk.doc_id, chunk.section_title)][chunk.chunk_index] = chunk

    expanded: list[SearchHit] = []
    seen_chunk_ids: set[str] = set()
    total_chars = 0
    for hit in selected_hits:
        group = by_section.get((hit.chunk.doc_id, hit.chunk.section_title), {})
        candidate_indices = [hit.chunk.chunk_index - 1, hit.chunk.chunk_index, hit.chunk.chunk_index + 1]
        for index in candidate_indices:
            chunk = group.get(index) or chunk_lookup.get(hit.chunk.chunk_id if index == hit.chunk.chunk_index else "")
            if chunk is None or chunk.chunk_id in seen_chunk_ids:
                continue
            if len(expanded) >= max_context_chunks:
                return expanded
            if total_chars + chunk.char_count > max_context_chars and expanded:
                return expanded
            derived_score = hit.score if chunk.chunk_id == hit.chunk.chunk_id else max(hit.score * 0.92, 0.01)
            expanded.append(
                SearchHit(
                    chunk_id=chunk.chunk_id,
                    score=float(derived_score),
                    bm25_score=hit.bm25_score,
                    vector_score=hit.vector_score,
                    chunk=chunk,
                    raw_bm25_score=hit.raw_bm25_score,
                    raw_vector_score=hit.raw_vector_score,
                )
            )
            seen_chunk_ids.add(chunk.chunk_id)
            total_chars += chunk.char_count
    return expanded


def _resolve_options(
    top_k: int,
    alpha: float,
    filters: dict[str, str | None] | None,
    candidate_pool: int,
    expand_neighbors: bool,
    max_context_chunks: int,
    max_context_chars: int,
    options: SearchOptions | None,
) -> SearchOptions:
    if options is not None:
        return options
    return SearchOptions(
        top_k=top_k,
        alpha=alpha,
        filters=filters or {},
        candidate_pool=candidate_pool,
        expand_neighbors=expand_neighbors,
        max_context_chunks=max_context_chunks,
        max_context_chars=max_context_chars,
    )


def search(
    query: str,
    chunks: list[ChunkRecord],
    top_k: int = DEFAULT_TOP_K,
    alpha: float = DEFAULT_ALPHA,
    filters: dict | None = None,
    candidate_pool: int = 24,
    expand_neighbors: bool = True,
    max_context_chunks: int = 8,
    max_context_chars: int = 7000,
    options: SearchOptions | None = None,
) -> list[SearchHit]:
    resolved = _resolve_options(top_k, alpha, filters, candidate_pool, expand_neighbors, max_context_chunks, max_context_chars, options)
    bm25_data = _load_pickle(PATHS.bm25_index_path)
    vector_data = _load_pickle(PATHS.vector_index_path)
    embeddings = np.load(PATHS.embeddings_path)

    filtered_indices = [index for index, chunk in enumerate(chunks) if _match_filters(chunk, resolved.filters)]
    if not filtered_indices:
        return []

    filtered_chunks = [chunks[index] for index in filtered_indices]
    query_tokens = tokenize(query)
    bm25_raw_scores = np.asarray(bm25_data["bm25"].get_scores(query_tokens), dtype=np.float32)[filtered_indices]
    query_embedding = embed_texts([query], backend=_query_backend(vector_data)).embeddings[0]
    faiss_score_lookup = _load_faiss_scores(query_embedding, len(chunks), resolved.candidate_pool)
    if faiss_score_lookup:
        vector_raw_scores = np.asarray([faiss_score_lookup.get(index, 0.0) for index in filtered_indices], dtype=np.float32)
    else:
        candidate_embeddings = embeddings[filtered_indices]
        vector_raw_scores = np.asarray(candidate_embeddings @ query_embedding, dtype=np.float32)

    bm25_norm = _normalize(bm25_raw_scores)
    vector_norm = _normalize(vector_raw_scores)
    final_scores = resolved.alpha * vector_norm + (1 - resolved.alpha) * bm25_norm
    order = np.argsort(final_scores)[::-1][: max(resolved.candidate_pool, resolved.top_k)]

    candidates = [
        _candidate_hit(
            chunk=filtered_chunks[idx],
            bm25_score=float(bm25_norm[idx]),
            vector_score=float(vector_norm[idx]),
            raw_bm25_score=float(bm25_raw_scores[idx]),
            raw_vector_score=float(vector_raw_scores[idx]),
            query_tokens=query_tokens,
            filters=resolved.filters,
        )
        for idx in order
    ]
    candidates.sort(key=lambda item: item.score, reverse=True)
    deduped = _dedupe_hits(candidates, resolved.top_k)
    if not resolved.expand_neighbors:
        return deduped
    return _expand_neighbor_hits(deduped, chunks, resolved.max_context_chunks, resolved.max_context_chars)
