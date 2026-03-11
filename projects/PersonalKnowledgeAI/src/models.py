from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SectionRecord:
    title: str
    source_url: str | None
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RawMarkdownDoc:
    source: str
    absolute_path: str
    relative_path: str
    title: str
    sections: list[SectionRecord]
    created_at: str
    updated_at: str


@dataclass
class DocumentRecord:
    doc_id: str
    source: str
    series: str
    title: str
    author: str
    file_path: str
    source_url: str | None
    primary_category: str | None
    topic_tags: list[str]
    attribute_tags: list[str]
    summary: str
    char_count: int
    created_at: str
    updated_at: str
    review_required: bool
    review_reason: str | None
    sections: list[SectionRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sections"] = [section.to_dict() for section in self.sections]
        return data


@dataclass
class ReviewCandidate:
    label: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "score": round(self.score, 4)}


@dataclass
class ReviewItem:
    doc_id: str
    file_path: str
    title: str
    candidate_primary_categories: list[ReviewCandidate]
    candidate_topic_tags: list[ReviewCandidate]
    current_attribute_tags: list[str]
    summary: str
    review_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "file_path": self.file_path,
            "title": self.title,
            "candidate_primary_categories": [item.to_dict() for item in self.candidate_primary_categories],
            "candidate_topic_tags": [item.to_dict() for item in self.candidate_topic_tags],
            "current_attribute_tags": self.current_attribute_tags,
            "summary": self.summary,
            "review_reason": self.review_reason,
        }


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    chunk_index: int
    source: str
    series: str
    doc_title: str
    section_title: str
    heading_path: list[str]
    source_url: str | None
    primary_category: str | None
    topic_tags: list[str]
    attribute_tags: list[str]
    text: str
    char_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchHit:
    chunk_id: str
    score: float
    bm25_score: float
    vector_score: float
    chunk: ChunkRecord
    raw_bm25_score: float = 0.0
    raw_vector_score: float = 0.0


@dataclass
class Taxonomy:
    primary_categories: list[str]
    topic_groups: dict[str, list[str]]
    attribute_groups: dict[str, list[str]]
    rules: dict[str, Any]
    keyword_hints: dict[str, Any]

    @property
    def topic_tags(self) -> list[str]:
        tags: list[str] = []
        for items in self.topic_groups.values():
            tags.extend(items)
        return tags

    @property
    def attribute_tags(self) -> list[str]:
        tags: list[str] = []
        for items in self.attribute_groups.values():
            tags.extend(items)
        return tags
