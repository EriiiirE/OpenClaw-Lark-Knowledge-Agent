from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from build_indexes import build_bm25_index, build_vector_index, save_faiss_index, save_json, save_pickle
from chunk_docs import chunk_documents
from classify_docs import classify_documents
from models import ChunkRecord, DocumentRecord, ReviewCandidate, ReviewItem, SectionRecord
from normalize_docs import normalize_documents
from review_docs import apply_review_updates
from settings import PATHS


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


def command_normalize(args, logger: logging.Logger) -> int:
    logger.info("Normalizing markdown sources into documents.jsonl")
    documents = normalize_documents()
    save_documents(documents)
    save_review_queue([])
    write_run_context("normalize", {"document_count": len(documents)})
    logger.info("Normalized %s documents", len(documents))
    return 0


def command_classify(args, logger: logging.Logger) -> int:
    documents = read_documents()
    if not documents:
        documents = normalize_documents()
    logger.info("Classifying %s documents with mode=%s", len(documents), args.mode)
    classified, review_items = classify_documents(documents, mode=args.mode)
    save_documents(classified)
    save_review_queue(review_items)
    PATHS.classification_cache_path.write_text(
        json.dumps(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "mode": args.mode,
                "review_count": len(review_items),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_run_context("classify", {"document_count": len(classified), "review_count": len(review_items)})
    logger.info("Classified %s documents; review queue size=%s", len(classified), len(review_items))
    return 0


def command_review(args, logger: logging.Logger) -> int:
    documents = read_documents()
    review_items = read_review_items()
    if not documents or not review_items:
        logger.info("No review items found.")
        return 0
    documents, remaining = apply_review_updates(documents, review_items, limit=args.limit, doc_id=args.doc_id)
    save_documents(documents)
    save_review_queue(remaining)
    PATHS.classification_cache_path.write_text(
        json.dumps({"updated_at": datetime.now().isoformat(timespec="seconds"), "remaining_review": len(remaining)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_run_context("review", {"remaining_review": len(remaining)})
    logger.info("Review completed. Remaining queue size=%s", len(remaining))
    return 0


def command_chunk(args, logger: logging.Logger) -> int:
    documents = read_documents()
    if not documents:
        logger.error("documents.jsonl not found. Run normalize or classify first.")
        return 1
    chunks = chunk_documents(documents)
    save_chunks(chunks)
    write_run_context("chunk", {"chunk_count": len(chunks)})
    logger.info("Generated %s chunks", len(chunks))
    return 0


def command_index(args, logger: logging.Logger) -> int:
    chunks = read_chunks()
    if not chunks:
        logger.error("chunks.jsonl not found. Run chunk first.")
        return 1
    logger.info("Building BM25 and vector indexes for %s chunks", len(chunks))
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
            "dimension": vector_data.get("dimension", 0),
            "index_type": vector_data.get("index_type", "array"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    write_run_context("index", {"chunk_count": len(chunks), "embedding_shape": list(embeddings.shape)})
    logger.info("Index build finished. Embedding shape=%s", tuple(embeddings.shape))
    return 0


def command_build_all(args, logger: logging.Logger) -> int:
    logger.info("Running full pipeline: normalize -> classify -> chunk -> index")
    command_normalize(args, logger)
    classify_args = argparse.Namespace(mode=args.mode)
    command_classify(classify_args, logger)
    command_chunk(args, logger)
    command_index(args, logger)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PersonalKnowledgeAI local knowledge base pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize_parser = subparsers.add_parser("normalize", help="Normalize markdown files into documents.jsonl")
    normalize_parser.set_defaults(func=command_normalize)

    classify_parser = subparsers.add_parser("classify", help="Classify documents into taxonomy labels")
    classify_parser.add_argument("--mode", choices=["rule", "auto", "llm"], default="rule")
    classify_parser.set_defaults(func=command_classify)

    review_parser = subparsers.add_parser("review", help="CLI review for low-confidence documents")
    review_parser.add_argument("--limit", type=int, default=None)
    review_parser.add_argument("--doc-id", default=None)
    review_parser.set_defaults(func=command_review)

    chunk_parser = subparsers.add_parser("chunk", help="Generate chunks.jsonl")
    chunk_parser.set_defaults(func=command_chunk)

    index_parser = subparsers.add_parser("index", help="Build BM25 and vector indexes")
    index_parser.set_defaults(func=command_index)

    build_all_parser = subparsers.add_parser("build-all", help="Run normalize, classify, chunk, and index")
    build_all_parser.add_argument("--mode", choices=["rule", "auto", "llm"], default="rule")
    build_all_parser.set_defaults(func=command_build_all)

    ingest_parser = subparsers.add_parser("ingest", help="Run full ingestion for desktop sources and /knowledge markdown files")
    ingest_parser.add_argument("--mode", choices=["rule", "auto", "llm"], default="rule")
    ingest_parser.set_defaults(func=command_build_all)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logger = setup_logger()
    return args.func(args, logger)


if __name__ == "__main__":
    raise SystemExit(main())
