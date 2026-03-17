from __future__ import annotations

import json
import pickle
from dataclasses import asdict, dataclass

import numpy as np

from models import ChunkRecord
from settings import PATHS, RUNTIME

try:
    import faiss
except Exception:  # pragma: no cover - optional dependency
    faiss = None


@dataclass
class VectorStoreProviderInfo:
    backend_id: str
    label: str
    available: bool
    configured: bool
    details: dict

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_json(path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_pickle(path):
    if not path.exists():
        return None
    with path.open("rb") as handle:
        return pickle.load(handle)


def load_local_vector_artifacts() -> dict:
    metadata = _safe_pickle(PATHS.vector_index_path) or _safe_json(PATHS.faiss_meta_path)
    embeddings = None
    if PATHS.embeddings_path.exists():
        try:
            embeddings = np.load(PATHS.embeddings_path)
        except Exception:
            embeddings = None
    index = None
    if faiss is not None and PATHS.faiss_index_path.exists():
        try:
            index = faiss.read_index(str(PATHS.faiss_index_path))
        except Exception:
            index = None
    return {
        "metadata": metadata,
        "embeddings": embeddings,
        "faiss_index": index,
    }


def list_vector_store_providers() -> list[VectorStoreProviderInfo]:
    providers = [
        VectorStoreProviderInfo(
            backend_id="local-faiss",
            label="Local BM25 + FAISS",
            available=True,
            configured=RUNTIME.vector_store.backend in {"local", "local-faiss"},
            details={
                "faiss_installed": faiss is not None,
                "bm25_path": str(PATHS.bm25_index_path),
                "faiss_path": str(PATHS.faiss_index_path),
            },
        )
    ]
    try:
        import pymilvus  # noqa: F401

        milvus_available = True
    except Exception:  # pragma: no cover - optional dependency
        milvus_available = False
    providers.append(
        VectorStoreProviderInfo(
            backend_id="milvus",
            label="Milvus",
            available=milvus_available,
            configured=RUNTIME.vector_store.backend == "milvus",
            details={
                "uri": RUNTIME.vector_store.milvus_uri,
                "db_name": RUNTIME.vector_store.milvus_db,
                "collection": RUNTIME.vector_store.milvus_collection,
            },
        )
    )
    return providers


def describe_vector_store_runtime() -> dict:
    local = load_local_vector_artifacts()
    metadata = local.get("metadata") or {}
    embeddings = local.get("embeddings")
    return {
        "configured_backend": RUNTIME.vector_store.backend,
        "default_backend": "local-faiss",
        "milvus_enabled": RUNTIME.vector_store.backend == "milvus",
        "local_index_ready": PATHS.bm25_index_path.exists() and PATHS.vector_index_path.exists() and PATHS.embeddings_path.exists(),
        "faiss_ready": PATHS.faiss_index_path.exists(),
        "dimension": metadata.get("dimension", int(embeddings.shape[1]) if getattr(embeddings, "ndim", 0) == 2 else 0),
        "embedding_model": metadata.get("model_name", ""),
        "embedding_backend": metadata.get("backend_id", ""),
    }


def sync_embeddings_to_backend(chunks: list[ChunkRecord], embeddings: np.ndarray, metadata: dict) -> dict:
    backend = RUNTIME.vector_store.backend
    if backend != "milvus":
        return {"backend": "local-faiss", "synced": False, "reason": "local backend selected"}
    try:
        from pymilvus import MilvusClient
    except Exception as exc:  # pragma: no cover - optional dependency
        return {"backend": "milvus", "synced": False, "reason": f"pymilvus unavailable: {exc}"}

    uri = RUNTIME.vector_store.milvus_uri
    if not uri:
        return {"backend": "milvus", "synced": False, "reason": "milvus uri not configured"}

    try:  # pragma: no cover - integration path
        client = MilvusClient(
            uri=uri,
            token=RUNTIME.vector_store.milvus_token or None,
            db_name=RUNTIME.vector_store.milvus_db or None,
        )
        collection_name = RUNTIME.vector_store.milvus_collection
        dimension = int(metadata.get("dimension") or 0)
        if not client.has_collection(collection_name=collection_name):
            client.create_collection(
                collection_name=collection_name,
                dimension=dimension,
                metric_type="IP",
                consistency_level="Bounded",
            )
        records = []
        for chunk, vector in zip(chunks, embeddings, strict=False):
            records.append(
                {
                    "id": chunk.chunk_id,
                    "vector": vector.tolist(),
                    "doc_id": chunk.doc_id,
                    "chunk_index": chunk.chunk_index,
                    "source": chunk.source,
                    "series": chunk.series,
                    "doc_title": chunk.doc_title,
                    "section_title": chunk.section_title,
                    "primary_category": chunk.primary_category or "",
                    "source_url": chunk.source_url or "",
                    "topic_tags": chunk.topic_tags,
                    "attribute_tags": chunk.attribute_tags,
                    "text": chunk.text,
                }
            )
        if records:
            client.upsert(collection_name=collection_name, data=records)
        return {"backend": "milvus", "synced": True, "row_count": len(records), "collection": collection_name}
    except Exception as exc:
        return {"backend": "milvus", "synced": False, "reason": str(exc)}
