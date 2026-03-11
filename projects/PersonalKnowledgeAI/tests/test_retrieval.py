from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_indexes import tokenize
from models import ChunkRecord, SearchHit
from retrieve import _expand_neighbor_hits, _match_filters


class RetrievalTests(unittest.TestCase):
    def test_tokenize_and_filter(self):
        chunk = ChunkRecord(
            chunk_id="chunk_1",
            doc_id="doc_1",
            chunk_index=0,
            source="jingyingrike",
            series="精英日课第五季",
            doc_title="AI",
            section_title="我们专栏用上了AI",
            heading_path=["AI", "我们专栏用上了AI"],
            source_url="https://example.com",
            primary_category="科技、AI 与互联网",
            topic_tags=["AI", "大模型"],
            attribute_tags=["精英日课", "主题文章"],
            text="AI 大模型 正在改变工作流。",
            char_count=20,
        )
        self.assertIn("ai", tokenize("AI 大模型"))
        self.assertTrue(_match_filters(chunk, {"source": "jingyingrike", "topic_tags": "AI"}))
        self.assertFalse(_match_filters(chunk, {"source": "yexiu_wechat"}))

    def test_expand_neighbor_hits(self):
        chunks = [
            ChunkRecord(
                chunk_id=f"chunk_{index}",
                doc_id="doc_1",
                chunk_index=index,
                source="jingyingrike",
                series="精英日课第一季",
                doc_title="B 选项",
                section_title="第一部分",
                heading_path=["B 选项", "第一部分"],
                source_url="https://example.com",
                primary_category="成长与人生",
                topic_tags=["成长"],
                attribute_tags=["精英日课"],
                text=f"内容 {index}" * 100,
                char_count=300,
            )
            for index in range(3)
        ]
        hit = SearchHit(chunk_id="chunk_1", score=0.9, bm25_score=0.8, vector_score=0.7, chunk=chunks[1])
        expanded = _expand_neighbor_hits([hit], chunks, max_context_chunks=8, max_context_chars=2000)
        self.assertEqual([item.chunk.chunk_id for item in expanded], ["chunk_0", "chunk_1", "chunk_2"])


if __name__ == "__main__":
    unittest.main()
