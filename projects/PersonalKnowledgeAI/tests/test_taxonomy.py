from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from taxonomy import load_taxonomy, validate_attribute_labels, validate_primary_label, validate_topic_labels


class TaxonomyTests(unittest.TestCase):
    def test_taxonomy_loads(self):
        taxonomy = load_taxonomy()
        self.assertIn("科技、AI 与互联网", taxonomy.primary_categories)
        self.assertIn("AI", taxonomy.topic_tags)
        self.assertIn("精英日课", taxonomy.attribute_tags)

    def test_primary_validation(self):
        taxonomy = load_taxonomy()
        self.assertTrue(validate_primary_label(taxonomy, "学习方法与教育"))
        self.assertFalse(validate_primary_label(taxonomy, "教育学"))

    def test_topic_and_attribute_validation(self):
        taxonomy = load_taxonomy()
        self.assertTrue(validate_topic_labels(taxonomy, ["AI", "大模型"]))
        self.assertFalse(validate_topic_labels(taxonomy, ["AI", "自我提升"]))
        self.assertTrue(validate_attribute_labels(taxonomy, ["精英日课", "主题文章"]))
        self.assertFalse(validate_attribute_labels(taxonomy, ["主题文章", "研究笔记"]))


if __name__ == "__main__":
    unittest.main()
