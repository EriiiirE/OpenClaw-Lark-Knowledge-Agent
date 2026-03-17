from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from env_loader import load_env_files


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parents[1]
load_env_files(BASE_DIR)
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
EMBEDDINGS_DIR = BASE_DIR / "embeddings"
VECTORSTORE_DIR = BASE_DIR / "vectorstore"
STATE_DIR = BASE_DIR / "state"
LOGS_DIR = BASE_DIR / "logs"
SRC_DIR = BASE_DIR / "src"

DESK_DIR = BASE_DIR.parent
JINGYINGRIKE_ROOT = DESK_DIR / "Jingyingrike" / "output_md"
CELUESHI_ROOT = DESK_DIR / "Celueshi" / "output_md"


@dataclass(frozen=True)
class Paths:
    base_dir: Path = BASE_DIR
    data_dir: Path = DATA_DIR
    knowledge_dir: Path = KNOWLEDGE_DIR
    embeddings_dir: Path = EMBEDDINGS_DIR
    vectorstore_dir: Path = VECTORSTORE_DIR
    state_dir: Path = STATE_DIR
    logs_dir: Path = LOGS_DIR
    src_dir: Path = SRC_DIR
    taxonomy_path: Path = SRC_DIR / "taxonomy.yaml"
    documents_path: Path = DATA_DIR / "documents.jsonl"
    review_queue_path: Path = DATA_DIR / "review_queue.jsonl"
    chunks_path: Path = DATA_DIR / "chunks.jsonl"
    embeddings_path: Path = EMBEDDINGS_DIR / "embeddings.npy"
    chunk_id_map_path: Path = DATA_DIR / "chunk_id_map.json"
    bm25_index_path: Path = STATE_DIR / "bm25_index.pkl"
    vector_index_path: Path = STATE_DIR / "vector_index.pkl"
    faiss_index_path: Path = VECTORSTORE_DIR / "chunks.faiss"
    faiss_meta_path: Path = VECTORSTORE_DIR / "chunks.meta.json"
    classification_cache_path: Path = STATE_DIR / "classification_cache.json"
    run_context_path: Path = STATE_DIR / "run_context.json"


PATHS = Paths()


OPENAI_API_KEY_ENV = "PKAI_API_KEY"
OPENAI_BASE_URL_ENV = "PKAI_BASE_URL"
OPENAI_MODEL_ENV = "PKAI_MODEL"

EMBEDDING_API_KEY_ENV = "PKAI_EMBED_API_KEY"
EMBEDDING_BASE_URL_ENV = "PKAI_EMBED_BASE_URL"
EMBEDDING_MODEL_ENV = "PKAI_EMBED_MODEL"
EMBEDDING_BACKEND_ENV = "PKAI_EMBED_BACKEND"

CHUNK_MODE_ENV = "PKAI_CHUNK_MODE"
VECTOR_STORE_BACKEND_ENV = "PKAI_VECTOR_STORE_BACKEND"
MILVUS_URI_ENV = "PKAI_MILVUS_URI"
MILVUS_TOKEN_ENV = "PKAI_MILVUS_TOKEN"
MILVUS_DB_ENV = "PKAI_MILVUS_DB"
MILVUS_COLLECTION_ENV = "PKAI_MILVUS_COLLECTION"

RERANK_ENABLED_ENV = "PKAI_RERANK_ENABLED"
API_HOST_ENV = "PKAI_API_HOST"
API_PORT_ENV = "PKAI_API_PORT"
MCP_TRANSPORT_ENV = "PKAI_MCP_TRANSPORT"
MCP_HOST_ENV = "PKAI_MCP_HOST"
MCP_PORT_ENV = "PKAI_MCP_PORT"

EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EMBED_BATCH_SIZE = 32
VECTOR_DIM_FALLBACK = 768

CHUNK_TARGET_CHARS = 900
CHUNK_MIN_CHARS = 400
CHUNK_MAX_CHARS = 1400
CHUNK_OVERLAP_CHARS = 120

DEFAULT_ALPHA = 0.45
DEFAULT_TOP_K = 8


@dataclass(frozen=True)
class ChunkingSettings:
    strategy: str = _env(CHUNK_MODE_ENV, "section-local") or "section-local"
    target_chars: int = _env_int("PKAI_CHUNK_TARGET_CHARS", CHUNK_TARGET_CHARS)
    min_chars: int = _env_int("PKAI_CHUNK_MIN_CHARS", CHUNK_MIN_CHARS)
    max_chars: int = _env_int("PKAI_CHUNK_MAX_CHARS", CHUNK_MAX_CHARS)
    overlap_chars: int = _env_int("PKAI_CHUNK_OVERLAP_CHARS", CHUNK_OVERLAP_CHARS)
    llm_enabled: bool = _env_bool("PKAI_CHUNK_LLM_ENABLED", False)
    llm_min_section_chars: int = _env_int("PKAI_CHUNK_LLM_MIN_SECTION_CHARS", 2200)
    llm_max_chunks_per_section: int = _env_int("PKAI_CHUNK_LLM_MAX_CHUNKS_PER_SECTION", 8)


@dataclass(frozen=True)
class EmbeddingSettings:
    backend: str = _env(EMBEDDING_BACKEND_ENV, "hashing") or "hashing"
    model_name: str = _env("PKAI_VECTOR_MODEL", EMBEDDING_MODEL_NAME) or EMBEDDING_MODEL_NAME
    batch_size: int = _env_int("PKAI_EMBED_BATCH_SIZE", EMBED_BATCH_SIZE)
    api_key: str | None = _env(EMBEDDING_API_KEY_ENV)
    base_url: str | None = _env(EMBEDDING_BASE_URL_ENV)
    api_model: str | None = _env(EMBEDDING_MODEL_ENV)
    dashscope_api_key: str | None = _env("DASHSCOPE_API_KEY")
    dashscope_model: str = _env("PKAI_DASHSCOPE_EMBED_MODEL", "text-embedding-v4") or "text-embedding-v4"


@dataclass(frozen=True)
class VectorStoreSettings:
    backend: str = _env(VECTOR_STORE_BACKEND_ENV, "local") or "local"
    milvus_uri: str | None = _env(MILVUS_URI_ENV)
    milvus_token: str | None = _env(MILVUS_TOKEN_ENV)
    milvus_db: str = _env(MILVUS_DB_ENV, "default") or "default"
    milvus_collection: str = _env(MILVUS_COLLECTION_ENV, "pkai_chunks") or "pkai_chunks"
    milvus_enabled: bool = _env_bool("PKAI_MILVUS_ENABLED", False)


@dataclass(frozen=True)
class RetrievalSettings:
    alpha: float = _env_float("PKAI_DEFAULT_ALPHA", DEFAULT_ALPHA)
    top_k: int = _env_int("PKAI_DEFAULT_TOP_K", DEFAULT_TOP_K)
    candidate_pool: int = _env_int("PKAI_DEFAULT_CANDIDATE_POOL", 24)
    expand_neighbors: bool = _env_bool("PKAI_EXPAND_NEIGHBORS", True)
    max_context_chunks: int = _env_int("PKAI_MAX_CONTEXT_CHUNKS", 8)
    max_context_chars: int = _env_int("PKAI_MAX_CONTEXT_CHARS", 7000)


@dataclass(frozen=True)
class GenerationSettings:
    enabled: bool = _env_bool("PKAI_GENERATION_ENABLED", True)
    api_key_env: str = OPENAI_API_KEY_ENV
    base_url_env: str = OPENAI_BASE_URL_ENV
    model_env: str = OPENAI_MODEL_ENV
    timeout_seconds: int = _env_int("PKAI_LLM_TIMEOUT_SECONDS", 90)


@dataclass(frozen=True)
class RerankSettings:
    enabled: bool = _env_bool(RERANK_ENABLED_ENV, False)
    mode: str = _env("PKAI_RERANK_MODE", "heuristic") or "heuristic"
    top_n: int = _env_int("PKAI_RERANK_TOP_N", 8)


@dataclass(frozen=True)
class ApiSettings:
    host: str = _env(API_HOST_ENV, "127.0.0.1") or "127.0.0.1"
    port: int = _env_int(API_PORT_ENV, 8787)


@dataclass(frozen=True)
class McpSettings:
    transport: str = _env(MCP_TRANSPORT_ENV, "stdio") or "stdio"
    host: str = _env(MCP_HOST_ENV, "127.0.0.1") or "127.0.0.1"
    port: int = _env_int(MCP_PORT_ENV, 8790)


@dataclass(frozen=True)
class RuntimeSettings:
    chunking: ChunkingSettings = ChunkingSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    vector_store: VectorStoreSettings = VectorStoreSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    generation: GenerationSettings = GenerationSettings()
    rerank: RerankSettings = RerankSettings()
    api: ApiSettings = ApiSettings()
    mcp: McpSettings = McpSettings()


RUNTIME = RuntimeSettings()
