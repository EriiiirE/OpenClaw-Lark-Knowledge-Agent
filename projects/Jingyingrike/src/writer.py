from __future__ import annotations

import re
from pathlib import Path

from models import ArticleRecord
from utils import ensure_dir


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')
MULTIPLE_UNDERSCORES = re.compile(r"_+")


def sanitize_filename(name: str) -> str:
    sanitized = INVALID_FILENAME_CHARS.sub("_", name).strip().strip(".")
    sanitized = MULTIPLE_UNDERSCORES.sub("_", sanitized)
    sanitized = sanitized[:120].strip().strip(".")
    return sanitized or "untitled_topic"


def render_topic_markdown(topic: str, records: list[ArticleRecord]) -> str:
    ordered_records = sorted(records, key=lambda item: item.order)
    chunks: list[str] = [f"# {topic}"]
    for record in ordered_records:
        chunks.append(
            "\n".join(
                [
                    "",
                    f"## {record.title}",
                    f"> 来源：{record.url}",
                    "",
                    record.content.strip(),
                ]
            ).rstrip()
        )
    return "\n\n".join(chunk for chunk in chunks if chunk).rstrip() + "\n"


def write_topic_markdown(topic: str, records: list[ArticleRecord], out_dir: Path) -> Path:
    ensure_dir(out_dir)
    target = out_dir / f"{sanitize_filename(topic)}.md"
    payload = render_topic_markdown(topic, records)
    target.write_text(payload, encoding="utf-8")
    return target
