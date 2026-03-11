from __future__ import annotations

import hashlib

from models import ChunkRecord, DocumentRecord
from settings import CHUNK_MAX_CHARS, CHUNK_MIN_CHARS, CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS
from utils_markdown import clean_text


def _chunk_text(text: str) -> list[str]:
    paragraphs = [part.strip() for part in clean_text(text).split("\n\n") if part.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= CHUNK_TARGET_CHARS:
            current = candidate
            continue
        if current and len(current) >= CHUNK_MIN_CHARS:
            chunks.append(current)
            overlap = current[-CHUNK_OVERLAP_CHARS:] if len(current) > CHUNK_OVERLAP_CHARS else current
            current = f"{overlap}\n\n{paragraph}".strip()
        else:
            current = candidate[:CHUNK_MAX_CHARS]
            chunks.append(current)
            current = candidate[CHUNK_MAX_CHARS - CHUNK_OVERLAP_CHARS :].strip()
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]


def chunk_documents(documents: list[DocumentRecord]) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    for doc in documents:
        chunk_index = 0
        for section in doc.sections:
            section_chunks = _chunk_text(section.text) or [clean_text(section.text)]
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
