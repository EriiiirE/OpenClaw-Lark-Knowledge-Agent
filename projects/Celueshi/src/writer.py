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
    return sanitized or "untitled"


def render_markdown(doc_title: str, records: list[ArticleRecord]) -> str:
    ordered = sorted(records, key=lambda item: item.order)
    chunks: list[str] = [f"# {doc_title}"]
    for record in ordered:
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


def write_markdown(category: str, section: str, records: list[ArticleRecord], out_dir: Path) -> Path:
    folder = ensure_dir(out_dir / sanitize_filename(category))
    target_name = section if section else category
    payload = render_markdown(target_name, records)
    target = folder / f"{sanitize_filename(target_name)}.md"
    target.write_text(payload, encoding="utf-8")
    return target
