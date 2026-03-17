from __future__ import annotations

from agent_runtime import kb_ask as kb_ask_action, kb_search as kb_search_action, kb_sources as kb_sources_action, kb_status as kb_status_action
from settings import RUNTIME


def _coerce_filters(
    source: str | None = None,
    series: str | None = None,
    primary_category: str | None = None,
    topic_tags: str | None = None,
    attribute_tags: str | None = None,
) -> dict[str, str | None]:
    return {
        "source": source,
        "series": series,
        "primary_category": primary_category,
        "topic_tags": topic_tags,
        "attribute_tags": attribute_tags,
    }


def create_mcp_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"MCP dependency is not installed: {exc}") from exc

    server = FastMCP("PersonalKnowledgeAI")

    @server.tool()
    def kb_search(
        query: str,
        top_k: int = 6,
        alpha: float = 0.45,
        source: str | None = None,
        series: str | None = None,
        primary_category: str | None = None,
        topic_tags: str | None = None,
        attribute_tags: str | None = None,
    ) -> dict:
        return kb_search_action(
            query=query,
            top_k=top_k,
            alpha=alpha,
            filters=_coerce_filters(source, series, primary_category, topic_tags, attribute_tags),
        )

    @server.tool()
    def kb_ask(
        query: str,
        top_k: int = 6,
        alpha: float = 0.45,
        prefer_llm: bool = True,
        source: str | None = None,
        series: str | None = None,
        primary_category: str | None = None,
        topic_tags: str | None = None,
        attribute_tags: str | None = None,
    ) -> dict:
        return kb_ask_action(
            query=query,
            top_k=top_k,
            alpha=alpha,
            prefer_llm=prefer_llm,
            filters=_coerce_filters(source, series, primary_category, topic_tags, attribute_tags),
        )

    @server.tool()
    def kb_status() -> dict:
        return kb_status_action()

    @server.tool()
    def kb_sources() -> dict:
        return kb_sources_action()

    return server


def run() -> None:
    server = create_mcp_server()
    try:  # pragma: no cover - depends on installed mcp version
        server.run(transport=RUNTIME.mcp.transport, host=RUNTIME.mcp.host, port=RUNTIME.mcp.port)
    except TypeError:
        server.run()
