from __future__ import annotations

from agent_runtime import ask_agent, kb_search, kb_sources
from agent_types import AgentResponse, SearchOptions
from pipeline_ops import command_build_index, doctor, get_provider_summary, read_chunks
from retrieval_pipeline import build_search_options


def load_chunks():
    return read_chunks()


def retrieve_context(query: str, filters: dict[str, str | None] | None = None, top_k: int = 6, alpha: float = 0.45):
    response = ask(query=query, filters=filters, top_k=top_k, alpha=alpha, prefer_llm=False)
    return response.evidence


def search(
    query: str,
    filters: dict[str, str | None] | None = None,
    top_k: int = 6,
    alpha: float = 0.45,
    history=None,
):
    return kb_search(query=query, filters=filters, top_k=top_k, alpha=alpha, history=history)


def ask(
    query: str,
    filters: dict[str, str | None] | None = None,
    top_k: int = 6,
    alpha: float = 0.45,
    prefer_llm: bool = True,
    history=None,
) -> AgentResponse:
    options = build_search_options(
        top_k=top_k,
        alpha=alpha,
        filters=filters,
        candidate_pool=max(top_k * 4, 24),
        expand_neighbors=True,
        max_context_chunks=8,
        max_context_chars=7000,
    )
    return ask_agent(query=query, history=history or [], options=options, prefer_llm=prefer_llm)


def build_index(config: dict | None = None):
    return command_build_index(config or {})


def sources():
    return kb_sources()


def providers():
    return get_provider_summary()


def status():
    return doctor()
