from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from env_loader import load_env_files


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

EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EMBED_BATCH_SIZE = 32
VECTOR_DIM_FALLBACK = 768

CHUNK_TARGET_CHARS = 900
CHUNK_MIN_CHARS = 400
CHUNK_MAX_CHARS = 1400
CHUNK_OVERLAP_CHARS = 120

DEFAULT_ALPHA = 0.45
DEFAULT_TOP_K = 8

OPENAI_API_KEY_ENV = "PKAI_API_KEY"
OPENAI_BASE_URL_ENV = "PKAI_BASE_URL"
OPENAI_MODEL_ENV = "PKAI_MODEL"
