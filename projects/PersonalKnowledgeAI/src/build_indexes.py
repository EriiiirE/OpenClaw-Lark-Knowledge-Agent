from __future__ import annotations

import json
import pickle
from pathlib import Path

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from embed_chunks import embed_texts
from models import ChunkRecord

try:
    import faiss
except Exception:  # pragma: no cover - optional at import time
    faiss = None


def tokenize(text: str) -> list[str]:
    return [token.strip().lower() for token in jieba.lcut(text) if token.strip()]


def build_bm25_index(chunks: list[ChunkRecord]) -> dict:
    corpus_tokens = [tokenize(chunk.text) for chunk in chunks]
    bm25 = BM25Okapi(corpus_tokens)
    return {"bm25": bm25, "chunk_ids": [chunk.chunk_id for chunk in chunks], "tokens": corpus_tokens}


def build_vector_index(chunks: list[ChunkRecord]) -> tuple[dict, np.ndarray, object | None]:
    texts = [chunk.text for chunk in chunks]
    embedding_result = embed_texts(texts)
    embeddings = embedding_result.embeddings.astype(np.float32)
    metadata = {
        "chunk_ids": [chunk.chunk_id for chunk in chunks],
        "model_name": embedding_result.model_name,
        "backend_id": getattr(embedding_result, "backend_id", ""),
        "dimension": int(embeddings.shape[1]) if embeddings.ndim == 2 and embeddings.size else 0,
        "index_type": "faiss" if faiss is not None else "array",
    }
    if len(texts) == 0 or faiss is None:
        return metadata, embeddings, None
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return metadata, embeddings, index


def save_pickle(path: Path, data) -> None:
    with path.open("wb") as handle:
        pickle.dump(data, handle)


def save_faiss_index(path: Path, index: object | None) -> None:
    if index is None or faiss is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(path))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
