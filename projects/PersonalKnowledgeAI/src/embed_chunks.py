from __future__ import annotations

from dataclasses import dataclass
import os

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize

from settings import EMBED_BATCH_SIZE, EMBEDDING_MODEL_NAME, VECTOR_DIM_FALLBACK


_MODEL_CACHE: dict[str, object] = {}


@dataclass
class EmbeddingResult:
    embeddings: np.ndarray
    model_name: str


def _hashing_embeddings(texts: list[str]) -> EmbeddingResult:
    vectorizer = HashingVectorizer(n_features=VECTOR_DIM_FALLBACK, alternate_sign=False, analyzer="char", ngram_range=(2, 4))
    matrix = vectorizer.transform(texts).astype(np.float32)
    dense = matrix.toarray()
    dense = normalize(dense)
    return EmbeddingResult(dense.astype(np.float32), "hashing-char-ngram")


def embed_texts(texts: list[str], backend: str | None = None) -> EmbeddingResult:
    if not texts:
        return EmbeddingResult(np.zeros((0, VECTOR_DIM_FALLBACK), dtype=np.float32), "empty")
    resolved_backend = (backend or os.getenv("PKAI_VECTOR_BACKEND", "hashing")).lower()
    if resolved_backend not in {"sentence-transformers", EMBEDDING_MODEL_NAME.lower()}:
        return _hashing_embeddings(texts)
    try:
        from sentence_transformers import SentenceTransformer

        model = _MODEL_CACHE.get(EMBEDDING_MODEL_NAME)
        if model is None:
            model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            _MODEL_CACHE[EMBEDDING_MODEL_NAME] = model
        embeddings = model.encode(texts, batch_size=EMBED_BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)
        return EmbeddingResult(np.asarray(embeddings, dtype=np.float32), EMBEDDING_MODEL_NAME)
    except Exception:
        return _hashing_embeddings(texts)
