from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from normalize_docs import infer_author, infer_series, stable_doc_id
from utils_markdown import clean_section_text


class NormalizationTests(unittest.TestCase):
    def test_series_inference(self):
        self.assertEqual(
            infer_series("jingyingrike", "Jingyingrike/output_md/第五季/AI.md", Path("D:/Desk/Jingyingrike/output_md/第五季/AI.md"), "AI"),
            "精英日课第五季",
        )
        self.assertEqual(
            infer_series("yexiu_wechat", "Celueshi/output_md/人学/人生之旅.md", Path("D:/Desk/Celueshi/output_md/人学/人生之旅.md"), "人生之旅"),
            "人生之旅",
        )
        self.assertEqual(
            infer_series("local_knowledge", "knowledge/产品/AI产品经理.md", Path("/knowledge/产品/AI产品经理.md"), "AI产品经理"),
            "产品",
        )

    def test_author_and_doc_id(self):
        self.assertEqual(infer_author("jingyingrike"), "万维钢")
        self.assertEqual(infer_author("yexiu_wechat"), "叶修")
        self.assertEqual(infer_author("local_knowledge"), "用户知识库")
        self.assertEqual(stable_doc_id("jingyingrike", "a/b.md", "AI"), stable_doc_id("jingyingrike", "a/b.md", "AI"))

    def test_source_specific_cleaning(self):
        wechat_text = "\n".join(
            [
                "叶修",
                "一个研究 思维方法 与 学习策略 的人",
                "新来的朋友点击上方 蓝字 关注 学习策略师",
                "即可免费获得深度思维、高效学习的方法",
                "真正的内容从这里开始。",
            ]
        )
        dedao_text = "\n".join(
            [
                "万维钢·精英日课",
                "《B选项》1:假如生活打击了你",
                "11分09秒",
                "｜音频转述师：怀沙｜",
                "核心内容开始。",
            ]
        )
        self.assertEqual(clean_section_text("yexiu_wechat", "测试", wechat_text), "真正的内容从这里开始。")
        self.assertEqual(clean_section_text("jingyingrike", "《B选项》1:假如生活打击了你", dedao_text), "核心内容开始。")


if __name__ == "__main__":
    unittest.main()
