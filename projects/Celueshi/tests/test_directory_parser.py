from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from directory_parser import assign_directory_entries


class DirectoryParserTests(unittest.TestCase):
    def test_assign_directory_entries_uses_font_size_levels(self) -> None:
        entries = assign_directory_entries(
            "https://mp.weixin.qq.com/s/demo",
            [
                {"kind": "heading", "text": "学科学习", "fontPx": 20},
                {"kind": "heading", "text": "语文", "fontPx": 17},
                {"kind": "link", "text": "文章A", "href": "https://mp.weixin.qq.com/s?a=1"},
                {"kind": "heading", "text": "数学", "fontPx": 17},
                {"kind": "link", "text": "文章B", "href": "https://mp.weixin.qq.com/s?a=2"},
                {"kind": "heading", "text": "信息源", "fontPx": 20},
                {"kind": "link", "text": "文章C", "href": "https://mp.weixin.qq.com/s?a=3"},
            ],
        )
        self.assertEqual([entry.category for entry in entries], ["学科学习", "学科学习", "信息源"])
        self.assertEqual([entry.section for entry in entries], ["语文", "数学", "信息源"])
