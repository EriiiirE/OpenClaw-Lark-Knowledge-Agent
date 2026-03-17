from __future__ import annotations

from typing import Any

from agent import answer_question
from agent_types import AgentResponse, ChatMessage, SearchOptions
from pipeline_ops import build_all, doctor, list_sources, read_chunks
from retrieval_pipeline import build_search_options, search_kb
from settings import DEFAULT_ALPHA, DEFAULT_TOP_K


def ask_agent(
    query: str,
    *,
    filters: dict[str, str | None] | None = None,
    top_k: int = DEFAULT_TOP_K,
    alpha: float = DEFAULT_ALPHA,
    prefer_llm: bool = True,
    history: list[ChatMessage] | None = None,
    options: SearchOptions | None = None,
) -> AgentResponse:
    chunks = read_chunks()
    resolved_options = options or build_search_options(top_k=top_k, alpha=alpha, filters=filters)
    return answer_question(
        user_query=query,
        chunks=chunks,
        history=history or [],
        options=resolved_options,
        prefer_llm=prefer_llm,
    )


def kb_search(
    query: str,
    *,
    filters: dict[str, str | None] | None = None,
    top_k: int = DEFAULT_TOP_K,
    alpha: float = DEFAULT_ALPHA,
    history: list[ChatMessage] | None = None,
) -> dict[str, Any]:
    result = search_kb(query=query, filters=filters, top_k=top_k, alpha=alpha, history=history)
    result.pop("raw_hits", None)
    return result


def kb_ask(
    query: str,
    *,
    filters: dict[str, str | None] | None = None,
    top_k: int = DEFAULT_TOP_K,
    alpha: float = DEFAULT_ALPHA,
    prefer_llm: bool = True,
    history: list[ChatMessage] | None = None,
) -> dict[str, Any]:
    response = ask_agent(
        query=query,
        filters=filters,
        top_k=top_k,
        alpha=alpha,
        prefer_llm=prefer_llm,
        history=history,
    )
    payload = response.to_dict()
    payload["query"] = query
    payload["tool"] = "kb.ask"
    return payload


def kb_sources() -> dict[str, Any]:
    payload = list_sources()
    payload["tool"] = "kb.sources"
    return payload


def kb_status() -> dict[str, Any]:
    payload = doctor()
    payload["tool"] = "kb.status"
    return payload


def kb_rebuild(mode: str = "rule") -> dict[str, Any]:
    payload = build_all(mode=mode)
    payload["tool"] = "kb.rebuild"
    return payload


def list_tools() -> list[dict[str, str]]:
    return [
        {"name": "kb.search", "description": "Hybrid retrieval with filters, trace, and chunk-level hits."},
        {"name": "kb.ask", "description": "Grounded answering with retrieval-only or LLM-enhanced mode."},
        {"name": "kb.sources", "description": "List available sources, series, and taxonomy filters."},
        {"name": "kb.status", "description": "Return runtime readiness, provider configuration, and corpus stats."},
        {"name": "kb.rebuild", "description": "Rebuild normalize/classify/chunk/index pipeline."},
    ]
