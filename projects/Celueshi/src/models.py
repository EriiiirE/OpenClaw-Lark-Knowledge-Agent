from __future__ import annotations

from dataclasses import asdict, dataclass
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


@dataclass(slots=True)
class DirectoryMeta:
    title: str
    url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DirectoryMeta":
        return cls(**payload)


@dataclass(slots=True)
class DirectoryEntry:
    id: str
    title: str
    url: str
    order: int
    category: str
    section: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DirectoryEntry":
        return cls(**payload)


@dataclass(slots=True)
class ArticleRecord:
    id: str
    category: str
    section: str
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
    category: str
    section: str
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
