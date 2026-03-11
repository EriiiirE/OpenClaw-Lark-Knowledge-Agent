from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extractor import extract_text_from_html_snapshot, normalize_extracted_text


PROMO_MARKERS = ["万维钢·精英日课6", "精英日课6", "下载得到", "得到APP", "扫码", "订阅", "课程宣传"]


class ExtractorTests(unittest.TestCase):
    def test_normalize_extracted_text_keeps_closing_sentence(self) -> None:
        text = "第一段\n咱们下一讲再说\n万维钢·精英日课6\n后续广告"
        result = normalize_extracted_text(text, PROMO_MARKERS)
        self.assertIn("咱们下一讲再说", result)
        self.assertNotIn("万维钢·精英日课6", result)

    def test_extract_text_from_html_snapshot_with_promo(self) -> None:
        html = (FIXTURES_DIR / "article_with_promo.html").read_text(encoding="utf-8")
        result = extract_text_from_html_snapshot(html, PROMO_MARKERS)
        self.assertIn("正文第一段", result)
        self.assertIn("咱们下一讲再说", result)
        self.assertNotIn("广告按钮", result)
        self.assertNotIn("万维钢·精英日课6", result)

    def test_extract_text_from_html_snapshot_without_promo(self) -> None:
        html = (FIXTURES_DIR / "article_without_promo.html").read_text(encoding="utf-8")
        result = extract_text_from_html_snapshot(html, PROMO_MARKERS)
        self.assertIn("正文第一段", result)
        self.assertIn("正文第二段", result)

    def test_normalize_extracted_text_handles_preface_without_book_brackets(self) -> None:
        text = "\n".join(
            [
                "展开目录",
                "设置文本",
                "发刊词：非专业知识",
                "万维钢·精英日课6（年度日更）",
                "发刊词：非专业知识",
                "11分56秒",
                "转述：怀沙",
                "不一样的星空，你好!",
                "欢迎来到精英日课第六季。",
                "我们需要「非专业知识」。",
                "首次发布: 2024年5月13日 下午3:37",
                "我的留言",
            ]
        )
        result = normalize_extracted_text(text, PROMO_MARKERS)
        self.assertIn("不一样的星空，你好!", result)
        self.assertIn("我们需要「非专业知识」。", result)
        self.assertNotIn("首次发布:", result)


if __name__ == "__main__":
    unittest.main()
