from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from article_extractor import clean_article_blocks


class ArticleExtractorTests(unittest.TestCase):
    def test_clean_article_blocks_truncates_before_signup(self) -> None:
        content = clean_article_blocks(
            [
                "策略师——叶修",
                "真正的正文第一段",
                "真正的正文第二段",
                "报名链接",
                "后面不该出现",
            ],
            title="测试标题",
        )
        self.assertIn("真正的正文第一段", content)
        self.assertIn("真正的正文第二段", content)
        self.assertNotIn("报名链接", content)
        self.assertNotIn("后面不该出现", content)
