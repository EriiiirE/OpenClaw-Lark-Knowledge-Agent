from __future__ import annotations

from collections.abc import MutableMapping

from agent_types import AgentResponse, ChatMessage, ChatSession


SESSION_KEY = "chat_session"


def _default_filters() -> dict[str, str | None]:
    return {
        "source": None,
        "series": None,
        "primary_category": None,
        "topic_tags": None,
        "attribute_tags": None,
    }


def ensure_chat_session(state: MutableMapping) -> ChatSession:
    session = state.get(SESSION_KEY)
    if isinstance(session, ChatSession):
        return session
    session = ChatSession.create(active_filters=_default_filters())
    state[SESSION_KEY] = session
    return session


def reset_chat_session(state: MutableMapping) -> ChatSession:
    session = ChatSession.create(active_filters=_default_filters())
    state[SESSION_KEY] = session
    return session


def update_active_filters(state: MutableMapping, filters: dict[str, str | None]) -> ChatSession:
    session = ensure_chat_session(state)
    session.active_filters = dict(filters)
    return session


def append_user_message(state: MutableMapping, content: str) -> ChatMessage:
    session = ensure_chat_session(state)
    message = ChatMessage.create(role="user", content=content)
    session.messages.append(message)
    return message


def append_assistant_message(state: MutableMapping, response: AgentResponse) -> ChatMessage:
    session = ensure_chat_session(state)
    message = ChatMessage.create(
        role="assistant",
        content=response.answer_markdown,
        metadata={
            "evidence": [item.to_dict() for item in response.evidence],
            "debug": response.debug,
            "standalone_query": response.standalone_query,
            "retrieval_mode": response.retrieval_mode,
            "confidence": response.confidence,
            "need_clarification": response.need_clarification,
        },
    )
    session.messages.append(message)
    return message


def get_history(state: MutableMapping) -> list[ChatMessage]:
    session = ensure_chat_session(state)
    return list(session.messages)
