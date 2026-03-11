from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from classify_docs import rule_classify
from models import DocumentRecord, SectionRecord


class ClassificationTests(unittest.TestCase):
    def test_rule_classify_ai_document(self):
        doc = DocumentRecord(
            doc_id="doc_test",
            source="jingyingrike",
            series="精英日课第五季",
            title="AI",
            author="万维钢",
            file_path="Jingyingrike/output_md/第五季/AI.md",
            source_url="https://example.com",
            primary_category=None,
            topic_tags=[],
            attribute_tags=[],
            summary="",
            char_count=1000,
            created_at="2026-03-01T00:00:00+08:00",
            updated_at="2026-03-01T00:00:00+08:00",
            review_required=False,
            review_reason=None,
            sections=[SectionRecord(title="我们专栏用上了AI", source_url="https://example.com", text="AI GPT 大模型 ChatGPT OpenAI 自动化 技术趋势")],
        )
        updated, _ = rule_classify(doc)
        self.assertEqual(updated.primary_category, "科技、AI 与互联网")
        self.assertIn("AI", updated.topic_tags)
        self.assertIn("精英日课", updated.attribute_tags)


if __name__ == "__main__":
    unittest.main()
