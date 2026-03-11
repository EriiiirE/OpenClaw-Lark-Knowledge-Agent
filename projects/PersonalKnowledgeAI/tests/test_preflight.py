from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import preflight


class PreflightTests(unittest.TestCase):
    def test_missing_required_files_reports_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            data_dir = base / "data"
            embeddings_dir = base / "embeddings"
            vectorstore_dir = base / "vectorstore"
            state_dir = base / "state"
            data_dir.mkdir()
            embeddings_dir.mkdir()
            vectorstore_dir.mkdir()
            state_dir.mkdir()

            original_paths = preflight.PATHS
            original_jingyingrike = preflight.JINGYINGRIKE_ROOT
            original_celueshi = preflight.CELUESHI_ROOT
            try:
                preflight.PATHS = SimpleNamespace(
                    documents_path=data_dir / "documents.jsonl",
                    chunks_path=data_dir / "chunks.jsonl",
                    review_queue_path=data_dir / "review_queue.jsonl",
                    bm25_index_path=state_dir / "bm25_index.pkl",
                    vector_index_path=state_dir / "vector_index.pkl",
                    embeddings_path=embeddings_dir / "embeddings.npy",
                    faiss_index_path=vectorstore_dir / "chunks.faiss",
                    faiss_meta_path=vectorstore_dir / "chunks.meta.json",
                    chunk_id_map_path=data_dir / "chunk_id_map.json",
                )
                preflight.JINGYINGRIKE_ROOT = base / "Jingyingrike" / "output_md"
                preflight.CELUESHI_ROOT = base / "Celueshi" / "output_md"
                status = preflight.run_preflight()
                self.assertFalse(status.ready)
                self.assertTrue(any("缺少 documents 文件" in issue for issue in status.issues))
            finally:
                preflight.PATHS = original_paths
                preflight.JINGYINGRIKE_ROOT = original_jingyingrike
                preflight.CELUESHI_ROOT = original_celueshi

    def test_review_queue_only_warns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            data_dir = base / "data"
            embeddings_dir = base / "embeddings"
            vectorstore_dir = base / "vectorstore"
            state_dir = base / "state"
            root_a = base / "Jingyingrike" / "output_md"
            root_b = base / "Celueshi" / "output_md"
            data_dir.mkdir(parents=True)
            embeddings_dir.mkdir(parents=True)
            vectorstore_dir.mkdir(parents=True)
            state_dir.mkdir(parents=True)
            root_a.mkdir(parents=True)
            root_b.mkdir(parents=True)

            (data_dir / "documents.jsonl").write_text('{"doc_id":"1"}\n', encoding="utf-8")
            (data_dir / "chunks.jsonl").write_text('{"chunk_id":"1"}\n', encoding="utf-8")
            (data_dir / "review_queue.jsonl").write_text('{"doc_id":"1"}\n', encoding="utf-8")
            (state_dir / "bm25_index.pkl").write_bytes(b"placeholder")
            (state_dir / "vector_index.pkl").write_bytes(b"placeholder")
            np.save(embeddings_dir / "embeddings.npy", np.zeros((1, 4), dtype=np.float32))
            (vectorstore_dir / "chunks.faiss").write_bytes(b"placeholder")
            (vectorstore_dir / "chunks.meta.json").write_text(json.dumps({"chunk_ids": ["1"]}), encoding="utf-8")
            (data_dir / "chunk_id_map.json").write_text(json.dumps({"chunk_ids": ["1"]}), encoding="utf-8")

            original_paths = preflight.PATHS
            original_jingyingrike = preflight.JINGYINGRIKE_ROOT
            original_celueshi = preflight.CELUESHI_ROOT
            try:
                preflight.PATHS = SimpleNamespace(
                    documents_path=data_dir / "documents.jsonl",
                    chunks_path=data_dir / "chunks.jsonl",
                    review_queue_path=data_dir / "review_queue.jsonl",
                    bm25_index_path=state_dir / "bm25_index.pkl",
                    vector_index_path=state_dir / "vector_index.pkl",
                    embeddings_path=embeddings_dir / "embeddings.npy",
                    faiss_index_path=vectorstore_dir / "chunks.faiss",
                    faiss_meta_path=vectorstore_dir / "chunks.meta.json",
                    chunk_id_map_path=data_dir / "chunk_id_map.json",
                )
                preflight.JINGYINGRIKE_ROOT = root_a
                preflight.CELUESHI_ROOT = root_b
                status = preflight.run_preflight()
                self.assertTrue(status.ready)
                self.assertEqual(status.stats["review_queue"], 1)
                self.assertTrue(status.warnings)
            finally:
                preflight.PATHS = original_paths
                preflight.JINGYINGRIKE_ROOT = original_jingyingrike
                preflight.CELUESHI_ROOT = original_celueshi


if __name__ == "__main__":
    unittest.main()
