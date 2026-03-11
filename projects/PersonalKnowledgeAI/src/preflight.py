from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from settings import CELUESHI_ROOT, JINGYINGRIKE_ROOT, PATHS


@dataclass
class PreflightStatus:
    ready: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def _count_jsonl_rows(path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def run_preflight() -> PreflightStatus:
    issues: list[str] = []
    warnings: list[str] = []

    required_files = {
        "documents": PATHS.documents_path,
        "chunks": PATHS.chunks_path,
        "bm25": PATHS.bm25_index_path,
        "vector": PATHS.vector_index_path,
        "embeddings": PATHS.embeddings_path,
        "faiss": PATHS.faiss_index_path,
        "faiss_meta": PATHS.faiss_meta_path,
        "chunk_id_map": PATHS.chunk_id_map_path,
    }
    for label, path in required_files.items():
        if not path.exists():
            issues.append(f"缺少 {label} 文件: {path.name}")

    if not JINGYINGRIKE_ROOT.exists():
        issues.append(f"知识源不可访问: {JINGYINGRIKE_ROOT}")
    if not CELUESHI_ROOT.exists():
        issues.append(f"知识源不可访问: {CELUESHI_ROOT}")

    document_count = _count_jsonl_rows(PATHS.documents_path)
    chunk_count = _count_jsonl_rows(PATHS.chunks_path)
    review_count = _count_jsonl_rows(PATHS.review_queue_path)

    if review_count > 0:
        warnings.append(f"当前还有 {review_count} 条 review_queue 待复核，不影响问答。")

    if PATHS.chunk_id_map_path.exists():
        try:
            chunk_id_map = json.loads(PATHS.chunk_id_map_path.read_text(encoding="utf-8"))
            mapped_count = len(chunk_id_map.get("chunk_ids", []))
            if chunk_count and mapped_count != chunk_count:
                issues.append(f"chunk_id_map 数量与 chunks.jsonl 不一致: {mapped_count} != {chunk_count}")
        except json.JSONDecodeError:
            issues.append("chunk_id_map.json 不是有效 JSON")

    if PATHS.embeddings_path.exists():
        try:
            embeddings = np.load(PATHS.embeddings_path, mmap_mode="r")
            embedding_rows = int(embeddings.shape[0]) if embeddings.ndim >= 1 else 0
            if chunk_count and embedding_rows != chunk_count:
                issues.append(f"embeddings 行数与 chunks.jsonl 不一致: {embedding_rows} != {chunk_count}")
        except Exception as exc:
            issues.append(f"embeddings.npy 无法读取: {exc}")

    return PreflightStatus(
        ready=not issues,
        issues=issues,
        warnings=warnings,
        stats={
            "documents": document_count,
            "chunks": chunk_count,
            "review_queue": review_count,
        },
    )
