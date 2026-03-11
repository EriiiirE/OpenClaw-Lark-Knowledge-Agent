from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import source_loader


class SourceLoaderTests(unittest.TestCase):
    def test_iter_markdown_sources_includes_knowledge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            knowledge_dir = base / "knowledge"
            knowledge_dir.mkdir(parents=True)
            (knowledge_dir / "产品").mkdir()
            target = knowledge_dir / "产品" / "AI产品经理.md"
            target.write_text("# AI产品经理\n\n## 概述\n内容", encoding="utf-8")

            original_paths = source_loader.PATHS
            original_jingyingrike = source_loader.JINGYINGRIKE_ROOT
            original_celueshi = source_loader.CELUESHI_ROOT
            try:
                source_loader.PATHS = SimpleNamespace(base_dir=base, knowledge_dir=knowledge_dir)
                source_loader.JINGYINGRIKE_ROOT = base / "Jingyingrike" / "output_md"
                source_loader.CELUESHI_ROOT = base / "Celueshi" / "output_md"
                items = source_loader.iter_markdown_sources()
                self.assertEqual(len(items), 1)
                source, _, relative = items[0]
                self.assertEqual(source, "local_knowledge")
                self.assertEqual(relative, "knowledge/产品/AI产品经理.md")
            finally:
                source_loader.PATHS = original_paths
                source_loader.JINGYINGRIKE_ROOT = original_jingyingrike
                source_loader.CELUESHI_ROOT = original_celueshi


if __name__ == "__main__":
    unittest.main()
