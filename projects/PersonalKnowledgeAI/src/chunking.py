from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from models import ChunkRecord, DocumentRecord
from rag_answer import chat_json, llm_available
from settings import RUNTIME
from utils_markdown import clean_text


_BOUNDARY_SPLIT_RE = re.compile(r"\n\s*---CHUNK---\s*\n", re.MULTILINE)


@dataclass(frozen=True)
class ChunkingConfig:
    strategy: str = RUNTIME.chunking.strategy
    target_chars: int = RUNTIME.chunking.target_chars
    min_chars: int = RUNTIME.chunking.min_chars
    max_chars: int = RUNTIME.chunking.max_chars
    overlap_chars: int = RUNTIME.chunking.overlap_chars
    llm_enabled: bool = RUNTIME.chunking.llm_enabled
    llm_min_section_chars: int = RUNTIME.chunking.llm_min_section_chars
    llm_max_chunks_per_section: int = RUNTIME.chunking.llm_max_chunks_per_section


def _chunk_text_local(text: str, config: ChunkingConfig) -> list[str]:
    paragraphs = [part.strip() for part in clean_text(text).split("\n\n") if part.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= config.target_chars:
            current = candidate
            continue
        if current and len(current) >= config.min_chars:
            chunks.append(current)
            overlap = current[-config.overlap_chars :] if len(current) > config.overlap_chars else current
            current = f"{overlap}\n\n{paragraph}".strip()
        else:
            current = candidate[: config.max_chars]
            chunks.append(current)
            current = candidate[config.max_chars - config.overlap_chars :].strip()
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]


def _normalize_llm_chunks(chunks: Iterable[str], config: ChunkingConfig) -> list[str]:
    normalized: list[str] = []
    for chunk in chunks:
        cleaned = clean_text(chunk)
        if not cleaned:
            continue
        if len(cleaned) <= config.max_chars:
            normalized.append(cleaned)
            continue
        normalized.extend(_chunk_text_local(cleaned, config))
    return normalized


def _llm_chunk_section(section_title: str, text: str, config: ChunkingConfig) -> list[str]:
    if not config.llm_enabled or not llm_available():
        return []
    if len(text) < config.llm_min_section_chars:
        return []
    prompt = (
        "你是中文知识库分块助手。请把下面的 section 划分成适合检索的语义块。"
        "不要改写内容，不要总结，不要补事实。"
        "只输出 JSON，格式为 {\"chunks\": [\"...\", \"...\"]}。"
        "每块尽量 400-1400 字，块与块尽量语义完整。"
        f"如果能切分的块数超过 {config.llm_max_chunks_per_section}，请合并到不超过这个数量。\n\n"
        f"section 标题：{section_title}\n\n{text}"
    )
    try:
        payload = chat_json([{"role": "user", "content": prompt}], temperature=0.0)
    except Exception:
        return []
    chunks = payload.get("chunks")
    if not isinstance(chunks, list):
        raw = str(payload.get("text", "")).strip()
        if raw:
            chunks = [item.strip() for item in _BOUNDARY_SPLIT_RE.split(raw) if item.strip()]
        else:
            return []
    return _normalize_llm_chunks((str(item) for item in chunks), config)


def chunk_section_text(section_title: str, text: str, config: ChunkingConfig | None = None) -> list[str]:
    resolved = config or ChunkingConfig()
    cleaned = clean_text(text)
    if not cleaned:
        return []
    llm_chunks = _llm_chunk_section(section_title, cleaned, resolved)
    if llm_chunks:
        return llm_chunks
    return _chunk_text_local(cleaned, resolved) or [cleaned]


def chunk_documents(documents: list[DocumentRecord], config: ChunkingConfig | None = None) -> list[ChunkRecord]:
    import hashlib

    resolved = config or ChunkingConfig()
    chunks: list[ChunkRecord] = []
    for doc in documents:
        chunk_index = 0
        for section in doc.sections:
            section_chunks = chunk_section_text(section.title, section.text, resolved)
            for text in section_chunks:
                digest = hashlib.sha1(f"{doc.doc_id}|{chunk_index}|{section.title}".encode("utf-8")).hexdigest()[:10]
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"chunk_{doc.doc_id}_{digest}",
                        doc_id=doc.doc_id,
                        chunk_index=chunk_index,
                        source=doc.source,
                        series=doc.series,
                        doc_title=doc.title,
                        section_title=section.title,
                        heading_path=[doc.title, section.title],
                        source_url=section.source_url or doc.source_url,
                        primary_category=doc.primary_category,
                        topic_tags=list(doc.topic_tags),
                        attribute_tags=list(doc.attribute_tags),
                        text=text,
                        char_count=len(text),
                    )
                )
                chunk_index += 1
    return chunks
