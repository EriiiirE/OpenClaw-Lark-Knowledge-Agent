from __future__ import annotations

from typing import Any

from agent import rewrite_query
from agent_types import ChatMessage, SearchOptions
from models import ChunkRecord, SearchHit
from pipeline_ops import read_chunks
from retrieve import search as raw_search
from settings import DEFAULT_ALPHA, DEFAULT_TOP_K


def build_search_options(
    *,
    top_k: int = DEFAULT_TOP_K,
    alpha: float = DEFAULT_ALPHA,
    filters: dict[str, str | None] | None = None,
    candidate_pool: int | None = None,
    expand_neighbors: bool = True,
    max_context_chunks: int = 8,
    max_context_chars: int = 7000,
) -> SearchOptions:
    resolved_top_k = max(1, int(top_k))
    return SearchOptions(
        top_k=resolved_top_k,
        alpha=float(alpha),
        filters=filters or {},
        candidate_pool=candidate_pool or max(resolved_top_k * 4, 24),
        expand_neighbors=expand_neighbors,
        max_context_chunks=max_context_chunks,
        max_context_chars=max_context_chars,
    )


def serialize_hit(hit: SearchHit) -> dict[str, Any]:
    chunk = hit.chunk
    return {
        "chunk_id": hit.chunk_id,
        "score": round(float(hit.score), 4),
        "bm25_score": round(float(hit.bm25_score), 4),
        "vector_score": round(float(hit.vector_score), 4),
        "raw_bm25_score": round(float(hit.raw_bm25_score), 4),
        "raw_vector_score": round(float(hit.raw_vector_score), 4),
        "source": chunk.source,
        "series": chunk.series,
        "doc_id": chunk.doc_id,
        "doc_title": chunk.doc_title,
        "section_title": chunk.section_title,
        "source_url": chunk.source_url,
        "primary_category": chunk.primary_category,
        "topic_tags": chunk.topic_tags,
        "attribute_tags": chunk.attribute_tags,
        "snippet": chunk.text[:220].rstrip() + ("..." if len(chunk.text) > 220 else ""),
        "char_count": chunk.char_count,
        "heading_path": chunk.heading_path,
    }


def search_kb(
    query: str,
    *,
    filters: dict[str, str | None] | None = None,
    top_k: int = DEFAULT_TOP_K,
    alpha: float = DEFAULT_ALPHA,
    history: list[ChatMessage] | None = None,
    chunks: list[ChunkRecord] | None = None,
    options: SearchOptions | None = None,
) -> dict[str, Any]:
    resolved_chunks = chunks if chunks is not None else read_chunks()
    resolved_options = options or build_search_options(top_k=top_k, alpha=alpha, filters=filters)
    standalone_query = rewrite_query(history or [], query)
    hits = raw_search(query=standalone_query, chunks=resolved_chunks, options=resolved_options)
    return {
        "query": query,
        "standalone_query": standalone_query,
        "retrieval_mode": "hybrid",
        "filters": resolved_options.filters,
        "top_k": resolved_options.top_k,
        "alpha": resolved_options.alpha,
        "candidate_pool": resolved_options.candidate_pool,
        "trace": {
            "rewrite_applied": standalone_query != query,
            "metadata_filter_count": sum(1 for value in resolved_options.filters.values() if value is not None),
            "section_dedup_enabled": True,
            "neighbor_expansion_enabled": resolved_options.expand_neighbors,
            "rerank_enabled": False,
        },
        "hits": [serialize_hit(hit) for hit in hits],
        "raw_hits": hits,
    }
