from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
TMP_DIR = PROJECT_ROOT / "tests" / "_tmp_writer"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from models import ArticleRecord
from writer import render_topic_markdown, sanitize_filename, write_topic_markdown


class WriterTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def test_sanitize_filename(self) -> None:
        self.assertEqual(sanitize_filename('再看一眼<>:"/\\\\|?*'), "再看一眼_")

    def test_render_topic_markdown(self) -> None:
        records = [
            ArticleRecord(
                id="2",
                topic="再看一眼",
                title="《再看一眼》2：注意力",
                url="https://www.dedao.cn/2",
                order=2,
                content="第二讲正文",
                fetched_at="2026-02-27T00:00:00+08:00",
            ),
            ArticleRecord(
                id="1",
                topic="再看一眼",
                title="《再看一眼》1：习惯化和去习惯化",
                url="https://www.dedao.cn/1",
                order=1,
                content="第一讲正文",
                fetched_at="2026-02-27T00:00:00+08:00",
            ),
        ]
        markdown = render_topic_markdown("再看一眼", records)
        self.assertIn("# 再看一眼", markdown)
        self.assertLess(markdown.index("《再看一眼》1：习惯化和去习惯化"), markdown.index("《再看一眼》2：注意力"))
        self.assertIn("> 来源：https://www.dedao.cn/1", markdown)

    def test_write_topic_markdown(self) -> None:
        record = ArticleRecord(
            id="1",
            topic="再看一眼",
            title="《再看一眼》1：习惯化和去习惯化",
            url="https://www.dedao.cn/1",
            order=1,
            content="第一讲正文",
            fetched_at="2026-02-27T00:00:00+08:00",
        )
        path = write_topic_markdown("再看一眼", [record], TMP_DIR)
        self.assertTrue(path.exists())
        self.assertIn("第一讲正文", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
