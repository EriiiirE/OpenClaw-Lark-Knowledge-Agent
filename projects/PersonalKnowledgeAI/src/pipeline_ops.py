from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from build_indexes import build_bm25_index, build_vector_index, save_faiss_index, save_json, save_pickle
from chunk_docs import chunk_documents
from classify_docs import classify_documents
from embedding_backends import describe_embedding_runtime, list_embedding_providers
from models import ChunkRecord, DocumentRecord, ReviewCandidate, ReviewItem, SectionRecord
from normalize_docs import normalize_documents
from preflight import run_preflight
from rag_answer import describe_generation_runtime
from review_docs import apply_review_updates
from settings import PATHS
from vector_stores import describe_vector_store_runtime, list_vector_store_providers, sync_embeddings_to_backend


def ensure_dirs() -> None:
    for directory in [PATHS.base_dir, PATHS.data_dir, PATHS.knowledge_dir, PATHS.embeddings_dir, PATHS.vectorstore_dir, PATHS.state_dir, PATHS.logs_dir]:
        directory.mkdir(parents=True, exist_ok=True)


def setup_logger() -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("pkai")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = PATHS.logs_dir / f"run_{timestamp}.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def _null_logger() -> logging.Logger:
    logger = logging.getLogger("pkai.null")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def _resolve_logger(logger: logging.Logger | None = None) -> logging.Logger:
    return logger or _null_logger()


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_documents(path: Path | None = None) -> list[DocumentRecord]:
    items: list[DocumentRecord] = []
    target = path or PATHS.documents_path
    if not target.exists():
        return items
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        data["sections"] = [SectionRecord(**section) for section in data.get("sections", [])]
        items.append(DocumentRecord(**data))
    return items


def read_review_items(path: Path | None = None) -> list[ReviewItem]:
    items: list[ReviewItem] = []
    target = path or PATHS.review_queue_path
    if not target.exists():
        return items
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        candidate_primary = data.get("candidate_primary_categories", [])
        candidate_topic = data.get("candidate_topic_tags", [])
        items.append(
            ReviewItem(
                doc_id=data["doc_id"],
                file_path=data["file_path"],
                title=data["title"],
                candidate_primary_categories=[ReviewCandidate(**item) for item in candidate_primary],
                candidate_topic_tags=[ReviewCandidate(**item) for item in candidate_topic],
                current_attribute_tags=data.get("current_attribute_tags", []),
                summary=data.get("summary", ""),
                review_reason=data.get("review_reason", "manual_review"),
            )
        )
    return items


def read_chunks(path: Path | None = None) -> list[ChunkRecord]:
    items: list[ChunkRecord] = []
    target = path or PATHS.chunks_path
    if not target.exists():
        return items
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        items.append(ChunkRecord(**json.loads(line)))
    return items


def save_documents(documents: list[DocumentRecord]) -> None:
    write_jsonl(PATHS.documents_path, [doc.to_dict() for doc in documents])


def save_review_queue(review_items: list[ReviewItem]) -> None:
    write_jsonl(PATHS.review_queue_path, [item.to_dict() for item in review_items])


def save_chunks(chunks: list[ChunkRecord]) -> None:
    write_jsonl(PATHS.chunks_path, [chunk.to_dict() for chunk in chunks])


def write_run_context(command: str, extra: dict | None = None) -> None:
    payload = {
        "last_command": command,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if extra:
        payload.update(extra)
    PATHS.run_context_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_run_context() -> dict[str, Any]:
    if not PATHS.run_context_path.exists():
        return {}
    try:
        return json.loads(PATHS.run_context_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def normalize_pipeline(logger: logging.Logger | None = None) -> dict:
    log = _resolve_logger(logger)
    log.info("Normalizing markdown sources into documents.jsonl")
    documents = normalize_documents()
    save_documents(documents)
    save_review_queue([])
    write_run_context("normalize", {"document_count": len(documents)})
    log.info("Normalized %s documents", len(documents))
    return {"document_count": len(documents)}


def classify_pipeline(mode: str = "rule", logger: logging.Logger | None = None) -> dict:
    log = _resolve_logger(logger)
    documents = read_documents()
    if not documents:
        documents = normalize_documents()
    log.info("Classifying %s documents with mode=%s", len(documents), mode)
    classified, review_items = classify_documents(documents, mode=mode)
    save_documents(classified)
    save_review_queue(review_items)
    PATHS.classification_cache_path.write_text(
        json.dumps(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "mode": mode,
                "review_count": len(review_items),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_run_context("classify", {"document_count": len(classified), "review_count": len(review_items), "mode": mode})
    log.info("Classified %s documents; review queue size=%s", len(classified), len(review_items))
    return {"document_count": len(classified), "review_count": len(review_items), "mode": mode}


def review_pipeline(limit: int | None = None, doc_id: str | None = None, logger: logging.Logger | None = None) -> dict:
    log = _resolve_logger(logger)
    documents = read_documents()
    review_items = read_review_items()
    if not documents or not review_items:
        log.info("No review items found.")
        return {"remaining_review": 0}
    documents, remaining = apply_review_updates(documents, review_items, limit=limit, doc_id=doc_id)
    save_documents(documents)
    save_review_queue(remaining)
    PATHS.classification_cache_path.write_text(
        json.dumps({"updated_at": datetime.now().isoformat(timespec="seconds"), "remaining_review": len(remaining)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_run_context("review", {"remaining_review": len(remaining)})
    log.info("Review completed. Remaining queue size=%s", len(remaining))
    return {"remaining_review": len(remaining)}


def chunk_pipeline(logger: logging.Logger | None = None) -> dict:
    log = _resolve_logger(logger)
    documents = read_documents()
    if not documents:
        raise FileNotFoundError("documents.jsonl not found. Run normalize or classify first.")
    chunks = chunk_documents(documents)
    save_chunks(chunks)
    write_run_context("chunk", {"chunk_count": len(chunks)})
    log.info("Generated %s chunks", len(chunks))
    return {"chunk_count": len(chunks)}


def index_pipeline(logger: logging.Logger | None = None) -> dict:
    log = _resolve_logger(logger)
    chunks = read_chunks()
    if not chunks:
        raise FileNotFoundError("chunks.jsonl not found. Run chunk first.")
    log.info("Building BM25 and vector indexes for %s chunks", len(chunks))
    bm25_data = build_bm25_index(chunks)
    vector_data, embeddings, faiss_index = build_vector_index(chunks)
    save_pickle(PATHS.bm25_index_path, bm25_data)
    save_pickle(PATHS.vector_index_path, vector_data)
    np.save(PATHS.embeddings_path, embeddings)
    save_faiss_index(PATHS.faiss_index_path, faiss_index)
    PATHS.chunk_id_map_path.write_text(
        json.dumps({"chunk_ids": [chunk.chunk_id for chunk in chunks], "updated_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_json(
        PATHS.faiss_meta_path,
        {
            "chunk_ids": [chunk.chunk_id for chunk in chunks],
            "model_name": vector_data.get("model_name"),
            "backend_id": vector_data.get("backend_id"),
            "dimension": vector_data.get("dimension", 0),
            "index_type": vector_data.get("index_type", "array"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    sync_result = sync_embeddings_to_backend(chunks, embeddings, vector_data)
    write_run_context(
        "index",
        {
            "chunk_count": len(chunks),
            "embedding_shape": list(embeddings.shape),
            "vector_store_sync": sync_result,
        },
    )
    log.info("Index build finished. Embedding shape=%s", tuple(embeddings.shape))
    return {
        "chunk_count": len(chunks),
        "embedding_shape": list(embeddings.shape),
        "vector_data": vector_data,
        "vector_store_sync": sync_result,
    }


def build_all(mode: str = "rule", logger: logging.Logger | None = None) -> dict:
    log = _resolve_logger(logger)
    log.info("Running full pipeline: normalize -> classify -> chunk -> index")
    normalized = normalize_pipeline(logger=log)
    classified = classify_pipeline(mode=mode, logger=log)
    chunked = chunk_pipeline(logger=log)
    indexed = index_pipeline(logger=log)
    return {
        "normalized": normalized,
        "classified": classified,
        "chunked": chunked,
        "indexed": indexed,
    }


def list_sources(chunks: list[ChunkRecord] | None = None) -> dict:
    resolved_chunks = chunks if chunks is not None else read_chunks()
    return {
        "source_count": len({chunk.source for chunk in resolved_chunks}),
        "series_count": len({chunk.series for chunk in resolved_chunks}),
        "sources": sorted({chunk.source for chunk in resolved_chunks}),
        "series": sorted({chunk.series for chunk in resolved_chunks}),
        "primary_categories": sorted({chunk.primary_category for chunk in resolved_chunks if chunk.primary_category}),
        "topic_tags": sorted({tag for chunk in resolved_chunks for tag in chunk.topic_tags}),
        "attribute_tags": sorted({tag for chunk in resolved_chunks for tag in chunk.attribute_tags}),
    }


def get_provider_summary() -> dict:
    return {
        "embedding": describe_embedding_runtime(),
        "embedding_providers": [provider.to_dict() for provider in list_embedding_providers()],
        "generation": describe_generation_runtime(),
        "vector_store": describe_vector_store_runtime(),
        "vector_store_providers": [provider.to_dict() for provider in list_vector_store_providers()],
    }


def doctor() -> dict:
    status = run_preflight()
    return {
        "ready": status.ready,
        "issues": status.issues,
        "warnings": status.warnings,
        "stats": status.stats,
        "run_context": read_run_context(),
        "providers": get_provider_summary(),
    }


def command_normalize(args, logger: logging.Logger) -> int:
    normalize_pipeline(logger=logger)
    return 0


def command_classify(args, logger: logging.Logger) -> int:
    classify_pipeline(mode=args.mode, logger=logger)
    return 0


def command_review(args, logger: logging.Logger) -> int:
    review_pipeline(limit=args.limit, doc_id=args.doc_id, logger=logger)
    return 0


def command_chunk(args, logger: logging.Logger) -> int:
    try:
        chunk_pipeline(logger=logger)
        return 0
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1


def command_index(args, logger: logging.Logger) -> int:
    try:
        index_pipeline(logger=logger)
        return 0
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1


def command_build_all(args, logger: logging.Logger) -> int:
    build_all(mode=args.mode, logger=logger)
    return 0


def command_doctor(args, logger: logging.Logger) -> int:
    print(json.dumps(doctor(), ensure_ascii=False, indent=2))
    return 0


def command_providers(args, logger: logging.Logger) -> int:
    print(json.dumps(get_provider_summary(), ensure_ascii=False, indent=2))
    return 0


def command_build_index(config: dict | None = None, logger: logging.Logger | None = None) -> dict:
    mode = str((config or {}).get("mode", "rule"))
    rebuild_all = bool((config or {}).get("rebuild_all", False))
    if rebuild_all:
        return build_all(mode=mode, logger=logger)
    return index_pipeline(logger=logger)


def build_cli_namespace(mode: str = "rule") -> argparse.Namespace:
    return argparse.Namespace(mode=mode)
