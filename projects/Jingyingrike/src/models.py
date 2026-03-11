from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


STATUS_PENDING = "pending"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_BLOCKED_RISK = "blocked_risk"
VALID_PROGRESS_STATUSES = {
    STATUS_PENDING,
    STATUS_SUCCESS,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_BLOCKED_RISK,
}

DEFAULT_PROMO_MARKERS = [
    "万维钢·精英日课6",
    "精英日课6",
    "下载得到",
    "得到APP",
    "扫码",
    "订阅",
    "课程宣传",
]


@dataclass(slots=True)
class CourseMeta:
    title: str
    url: str
    promo_markers: list[str] = field(default_factory=lambda: list(DEFAULT_PROMO_MARKERS))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CourseMeta":
        return cls(**payload)


@dataclass(slots=True)
class CatalogEntry:
    id: str
    title: str
    url: str
    order: int
    source_index: int | None = None
    section_topic: str | None = None
    raw_topic: str | None = None
    assigned_topic: str | None = None
    is_qa: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CatalogEntry":
        return cls(**payload)


@dataclass(slots=True)
class ArticleRecord:
    id: str
    topic: str
    title: str
    url: str
    order: int
    content: str
    fetched_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArticleRecord":
        return cls(**payload)


@dataclass(slots=True)
class ProgressRecord:
    id: str
    status: str
    attempts: int
    title: str
    url: str
    topic: str | None
    cache_path: str | None
    last_error: str | None
    updated_at: str

    def __post_init__(self) -> None:
        if self.status not in VALID_PROGRESS_STATUSES:
            raise ValueError(f"Invalid status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProgressRecord":
        return cls(**payload)
