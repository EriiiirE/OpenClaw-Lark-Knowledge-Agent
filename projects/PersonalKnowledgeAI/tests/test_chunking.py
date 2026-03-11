from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chunk_docs import chunk_documents
from models import DocumentRecord, SectionRecord


class ChunkingTests(unittest.TestCase):
    def test_chunk_generation(self):
        doc = DocumentRecord(
            doc_id="doc_test",
            source="jingyingrike",
            series="精英日课第一季",
            title="测试标题",
            author="万维钢",
            file_path="Jingyingrike/output_md/第一季/test.md",
            source_url="https://example.com",
            primary_category="决策与方法论",
            topic_tags=["决策", "方法论"],
            attribute_tags=["精英日课", "主题文章"],
            summary="summary",
            char_count=2000,
            created_at="2026-03-01T00:00:00+08:00",
            updated_at="2026-03-01T00:00:00+08:00",
            review_required=False,
            review_reason=None,
            sections=[SectionRecord(title="第一节", source_url="https://example.com", text=("段落一。" * 300))],
        )
        chunks = chunk_documents([doc])
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(chunks[0].doc_id, "doc_test")
        self.assertEqual(chunks[0].section_title, "第一节")


if __name__ == "__main__":
    unittest.main()
