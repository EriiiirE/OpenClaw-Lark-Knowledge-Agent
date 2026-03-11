from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from models import ArticleRecord
from writer import write_markdown


class WriterTests(unittest.TestCase):
    def test_write_markdown_creates_category_folder(self) -> None:
        tmp_path = Path(__file__).resolve().parent / "_tmp_writer"
        if tmp_path.exists():
            for child in sorted(tmp_path.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                else:
                    child.rmdir()
            tmp_path.rmdir()

        target = write_markdown(
            "学科学习",
            "语文",
            [
                ArticleRecord(
                    id="1",
                    category="学科学习",
                    section="语文",
                    title="文章一",
                    url="https://mp.weixin.qq.com/s/demo",
                    order=1,
                    content="正文",
                    fetched_at="2026-03-04T16:00:00+08:00",
                )
            ],
            tmp_path,
        )
        self.assertEqual(target.parent.name, "学科学习")
        self.assertEqual(target.name, "语文.md")
        payload = target.read_text(encoding="utf-8")
        self.assertIn("# 语文", payload)
        self.assertIn("## 文章一", payload)
