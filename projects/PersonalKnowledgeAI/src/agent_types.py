from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4


@dataclass
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, role: Literal["user", "assistant"], content: str, metadata: dict[str, Any] | None = None) -> "ChatMessage":
        return cls(role=role, content=content, timestamp=datetime.now().isoformat(timespec="seconds"), metadata=metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChatSession:
    session_id: str
    messages: list[ChatMessage]
    active_filters: dict[str, str | None]

    @classmethod
    def create(cls, active_filters: dict[str, str | None] | None = None) -> "ChatSession":
        return cls(session_id=f"chat_{uuid4().hex[:10]}", messages=[], active_filters=active_filters or {})


@dataclass(frozen=True)
class SearchOptions:
    top_k: int = 6
    alpha: float = 0.45
    filters: dict[str, str | None] = field(default_factory=dict)
    candidate_pool: int = 24
    expand_neighbors: bool = True
    max_context_chunks: int = 8
    max_context_chars: int = 7000


@dataclass
class EvidenceItem:
    ref_id: str
    chunk_id: str
    doc_title: str
    section_title: str
    source: str
    series: str
    source_url: str | None
    snippet: str
    score: float
    full_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResponse:
    answer_markdown: str
    evidence: list[EvidenceItem]
    standalone_query: str
    retrieval_mode: str
    confidence: str
    need_clarification: bool
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_markdown": self.answer_markdown,
            "evidence": [item.to_dict() for item in self.evidence],
            "standalone_query": self.standalone_query,
            "retrieval_mode": self.retrieval_mode,
            "confidence": self.confidence,
            "need_clarification": self.need_clarification,
            "debug": self.debug,
        }
