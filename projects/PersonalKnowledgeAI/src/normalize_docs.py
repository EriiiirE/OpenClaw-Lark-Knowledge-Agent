from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from models import DocumentRecord, RawMarkdownDoc, SectionRecord
from source_loader import iter_markdown_sources
from utils_markdown import clean_section_text, clean_text, extract_char_count, parse_markdown_document, read_markdown_text


SEASON_MAP = {
    "第一季": "精英日课第一季",
    "第二季": "精英日课第二季",
    "第三季": "精英日课第三季",
    "第四季": "精英日课第四季",
    "第五季": "精英日课第五季",
    "第六季": "精英日课第六季",
}


def isoformat_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def infer_series(source: str, relative_path: str, path: Path, title: str) -> str:
    parts = Path(relative_path).parts
    if source == "jingyingrike":
        if len(parts) >= 3:
            return SEASON_MAP.get(parts[2], parts[2])
        return "精英日课"
    if source == "local_knowledge":
        if len(parts) >= 2:
            return parts[1] if parts[0] == "knowledge" and len(parts) > 2 else path.stem
        return path.stem or title
    return path.stem or title


def infer_author(source: str) -> str:
    if source == "jingyingrike":
        return "万维钢"
    if source == "yexiu_wechat":
        return "叶修"
    return "用户知识库"


def stable_doc_id(source: str, relative_path: str, title: str) -> str:
    digest = hashlib.sha1(f"{source}|{relative_path}|{title}".encode("utf-8")).hexdigest()[:12]
    return f"doc_{source}_{digest}"


def load_raw_docs() -> list[RawMarkdownDoc]:
    docs: list[RawMarkdownDoc] = []
    for source, absolute_path, relative_path in iter_markdown_sources():
        text = read_markdown_text(absolute_path)
        try:
            title, sections = parse_markdown_document(text)
        except Exception:
            title = path_stem = absolute_path.stem
            sections = [SectionRecord(title=path_stem, source_url=None, text=clean_text(text))]
        cleaned_sections: list[SectionRecord] = []
        for section in sections:
            cleaned_text = clean_section_text(source, section.title, section.text)
            if not cleaned_text:
                continue
            cleaned_sections.append(
                SectionRecord(
                    title=section.title,
                    source_url=section.source_url,
                    text=cleaned_text,
                )
            )
        stat = absolute_path.stat()
        docs.append(
            RawMarkdownDoc(
                source=source,
                absolute_path=str(absolute_path),
                relative_path=relative_path.replace("\\", "/"),
                title=title,
                sections=cleaned_sections,
                created_at=isoformat_from_timestamp(stat.st_ctime),
                updated_at=isoformat_from_timestamp(stat.st_mtime),
            )
        )
    return docs


def normalize_documents() -> list[DocumentRecord]:
    records: list[DocumentRecord] = []
    for raw in load_raw_docs():
        path = Path(raw.absolute_path)
        source_url = raw.sections[0].source_url if raw.sections else None
        records.append(
            DocumentRecord(
                doc_id=stable_doc_id(raw.source, raw.relative_path, raw.title),
                source=raw.source,
                series=infer_series(raw.source, raw.relative_path, path, raw.title),
                title=raw.title,
                author=infer_author(raw.source),
                file_path=raw.relative_path,
                source_url=source_url,
                primary_category=None,
                topic_tags=[],
                attribute_tags=[],
                summary="",
                char_count=extract_char_count(raw.sections),
                created_at=raw.created_at,
                updated_at=raw.updated_at,
                review_required=False,
                review_reason=None,
                sections=raw.sections,
            )
        )
    return records
