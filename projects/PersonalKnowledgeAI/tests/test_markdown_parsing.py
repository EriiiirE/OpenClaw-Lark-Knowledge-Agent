from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils_markdown import parse_markdown_document


class MarkdownParsingTests(unittest.TestCase):
    def test_parse_h1_h2_and_source(self):
        text = """# AI

## 第一篇
> 来源：https://example.com/1

正文一

## 第二篇
> 来源：https://example.com/2

正文二
"""
        title, sections = parse_markdown_document(text)
        self.assertEqual(title, "AI")
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0].title, "第一篇")
        self.assertEqual(sections[0].source_url, "https://example.com/1")
        self.assertIn("正文二", sections[1].text)


if __name__ == "__main__":
    unittest.main()
