from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import numpy as np
import requests
from requests import RequestException
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize

from settings import RUNTIME, VECTOR_DIM_FALLBACK


_MODEL_CACHE: dict[str, object] = {}


@dataclass
class EmbeddingResult:
    embeddings: np.ndarray
    model_name: str
    backend_id: str


@dataclass(frozen=True)
class EmbeddingProviderInfo:
    provider_id: str
    label: str
    available: bool
    kind: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "available": self.available,
            "kind": self.kind,
            "details": self.details,
        }


def _hashing_embeddings(texts: list[str]) -> EmbeddingResult:
    vectorizer = HashingVectorizer(n_features=VECTOR_DIM_FALLBACK, alternate_sign=False, analyzer="char", ngram_range=(2, 4))
    matrix = vectorizer.transform(texts).astype(np.float32)
    dense = matrix.toarray()
    dense = normalize(dense)
    return EmbeddingResult(dense.astype(np.float32), "hashing-char-ngram", "hashing")


def _sentence_transformer_embeddings(texts: list[str], model_name: str) -> EmbeddingResult:
    from sentence_transformers import SentenceTransformer

    model = _MODEL_CACHE.get(model_name)
    if model is None:
        model = SentenceTransformer(model_name)
        _MODEL_CACHE[model_name] = model
    embeddings = model.encode(texts, batch_size=RUNTIME.embedding.batch_size, normalize_embeddings=True, show_progress_bar=False)
    return EmbeddingResult(np.asarray(embeddings, dtype=np.float32), model_name, "sentence-transformers")


def _normalize_base_url(base_url: str) -> str:
    stripped = base_url.rstrip("/")
    return stripped[:-11] if stripped.endswith("/embeddings") else stripped


def _openai_compatible_embeddings(texts: list[str], *, base_url: str, api_key: str, model_name: str, backend_id: str) -> EmbeddingResult:
    endpoint = _normalize_base_url(base_url) + "/embeddings"
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"input": texts, "model": model_name},
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or []
    embeddings = [item.get("embedding") for item in data if isinstance(item, dict) and isinstance(item.get("embedding"), list)]
    if len(embeddings) != len(texts):
        raise RuntimeError(f"Embedding provider {backend_id} returned {len(embeddings)} vectors for {len(texts)} texts.")
    return EmbeddingResult(np.asarray(embeddings, dtype=np.float32), model_name, backend_id)


def _dashscope_embeddings(texts: list[str], *, api_key: str, model_name: str) -> EmbeddingResult:
    return _openai_compatible_embeddings(
        texts,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=api_key,
        model_name=model_name,
        backend_id="dashscope",
    )


def list_embedding_providers() -> list[EmbeddingProviderInfo]:
    settings = RUNTIME.embedding
    return [
        EmbeddingProviderInfo("hashing", "Hashing char n-gram", True, "local", {"dimension": VECTOR_DIM_FALLBACK}),
        EmbeddingProviderInfo(
            "sentence-transformers",
            settings.model_name,
            True,
            "local",
            {"model_name": settings.model_name},
        ),
        EmbeddingProviderInfo(
            "openai-compatible",
            settings.api_model or "openai-compatible",
            bool(settings.api_key and settings.base_url and settings.api_model),
            "remote",
            {"base_url": settings.base_url or "", "model_name": settings.api_model or ""},
        ),
        EmbeddingProviderInfo(
            "siliconflow",
            settings.api_model or "siliconflow-compatible",
            bool(settings.api_key and settings.base_url and settings.api_model and "siliconflow" in (settings.base_url or "").lower()),
            "remote",
            {"base_url": settings.base_url or "", "model_name": settings.api_model or ""},
        ),
        EmbeddingProviderInfo(
            "dashscope",
            settings.dashscope_model,
            bool(settings.dashscope_api_key),
            "remote",
            {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model_name": settings.dashscope_model},
        ),
    ]


def describe_embedding_runtime() -> dict[str, Any]:
    return {
        "default_backend": RUNTIME.embedding.backend,
        "providers": [item.to_dict() for item in list_embedding_providers()],
    }


def embed_texts(texts: list[str], backend: str | None = None, model_name: str | None = None) -> EmbeddingResult:
    if not texts:
        return EmbeddingResult(np.zeros((0, VECTOR_DIM_FALLBACK), dtype=np.float32), "empty", "empty")

    resolved_backend = (backend or RUNTIME.embedding.backend or "hashing").lower()
    resolved_model = model_name or RUNTIME.embedding.model_name

    try:
        if resolved_backend in {"sentence-transformers", resolved_model.lower()}:
            return _sentence_transformer_embeddings(texts, resolved_model)
        if resolved_backend == "dashscope":
            if not RUNTIME.embedding.dashscope_api_key:
                raise RuntimeError("DASHSCOPE_API_KEY is not configured.")
            return _dashscope_embeddings(texts, api_key=RUNTIME.embedding.dashscope_api_key, model_name=RUNTIME.embedding.dashscope_model)
        if resolved_backend in {"openai-compatible", "siliconflow"}:
            if not (RUNTIME.embedding.api_key and RUNTIME.embedding.base_url and (model_name or RUNTIME.embedding.api_model)):
                raise RuntimeError("OpenAI-compatible embedding backend is not fully configured.")
            return _openai_compatible_embeddings(
                texts,
                base_url=RUNTIME.embedding.base_url,
                api_key=RUNTIME.embedding.api_key,
                model_name=model_name or RUNTIME.embedding.api_model or resolved_model,
                backend_id=resolved_backend,
            )
        return _hashing_embeddings(texts)
    except (RequestException, ValueError, KeyError, RuntimeError, json.JSONDecodeError, ImportError):
        if resolved_backend == "hashing":
            raise
        return _hashing_embeddings(texts)
