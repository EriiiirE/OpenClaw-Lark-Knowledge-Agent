from __future__ import annotations

from agent import answer_question
from agent_types import AgentResponse, SearchOptions
from main import read_chunks


def load_chunks():
    return read_chunks()


def retrieve_context(query: str, filters: dict[str, str | None] | None = None, top_k: int = 6, alpha: float = 0.45):
    response = ask(query=query, filters=filters, top_k=top_k, alpha=alpha, prefer_llm=False)
    return response.evidence


def ask(
    query: str,
    filters: dict[str, str | None] | None = None,
    top_k: int = 6,
    alpha: float = 0.45,
    prefer_llm: bool = True,
    history=None,
) -> AgentResponse:
    chunks = load_chunks()
    options = SearchOptions(
        top_k=top_k,
        alpha=alpha,
        filters=filters or {},
        candidate_pool=max(top_k * 4, 24),
        expand_neighbors=True,
        max_context_chunks=8,
        max_context_chars=7000,
    )
    return answer_question(user_query=query, chunks=chunks, history=history or [], options=options, prefer_llm=prefer_llm)
