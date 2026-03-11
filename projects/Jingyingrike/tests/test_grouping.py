from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from grouping import (
    assign_topics,
    extract_special_topic,
    extract_topic,
    is_qa_title,
    normalize_section_topic,
    ordered_topic_names,
    select_topic_names,
)
from models import CatalogEntry


class GroupingTests(unittest.TestCase):
    def test_extract_topic(self) -> None:
        self.assertEqual(extract_topic("《再看一眼》1：习惯化和去习惯化"), "再看一眼")

    def test_is_qa_title(self) -> None:
        self.assertTrue(is_qa_title("问答：如何理解去习惯化？"))
        self.assertTrue(is_qa_title("Q&A: habit"))
        self.assertFalse(is_qa_title("《再看一眼》1：习惯化和去习惯化"))

    def test_extract_special_topic(self) -> None:
        self.assertEqual(extract_special_topic("发刊词：非专业知识"), "发刊词")
        self.assertEqual(extract_special_topic("第五季结束语：智慧和智能"), "第五季结束语")
        self.assertIsNone(extract_special_topic("总结：如何学习"))

    def test_normalize_section_topic(self) -> None:
        self.assertEqual(normalize_section_topic("《内部掌控，外部影响》(14讲)"), "内部掌控，外部影响")
        self.assertEqual(normalize_section_topic("*价值观向下兼容*(23讲)"), "价值观向下兼容")
        self.assertEqual(normalize_section_topic("发刊词(1讲)"), "发刊词")

    def test_assign_topics_with_section_topic(self) -> None:
        entries = [
            CatalogEntry(
                id="1",
                title="中年最大的危机是社交封闭",
                url="https://www.dedao.cn/1",
                order=1,
                section_topic="非专业知识·价值对齐(18讲)",
            ),
            CatalogEntry(
                id="2",
                title="优秀人才的三个特质",
                url="https://www.dedao.cn/2",
                order=2,
                section_topic="非专业知识·价值对齐(18讲)",
            ),
        ]
        assigned, unassigned = assign_topics(entries)
        self.assertEqual([entry.assigned_topic for entry in assigned], ["非专业知识·价值对齐", "非专业知识·价值对齐"])
        self.assertEqual(unassigned, [])

    def test_assign_topics_with_qa(self) -> None:
        entries = [
            CatalogEntry(id="1", title="《再看一眼》1：习惯化和去习惯化", url="https://www.dedao.cn/1", order=1),
            CatalogEntry(id="2", title="《再看一眼》2：注意力", url="https://www.dedao.cn/2", order=2),
            CatalogEntry(id="3", title="问答：如何理解去习惯化？", url="https://www.dedao.cn/3", order=3),
            CatalogEntry(id="4", title="《另一本》1：开篇", url="https://www.dedao.cn/4", order=4),
        ]
        assigned, unassigned = assign_topics(entries)
        self.assertEqual(
            [entry.assigned_topic for entry in assigned],
            ["再看一眼", "再看一眼", "再看一眼", "另一本"],
        )
        self.assertEqual(unassigned, [])

    def test_assign_topics_uses_section_for_summary(self) -> None:
        entries = [
            CatalogEntry(
                id="1",
                title="《内部掌控，外部影响》1：内圣外王的勇气",
                url="https://www.dedao.cn/1",
                order=1,
                section_topic="《内部掌控，外部影响》(14讲)",
            ),
            CatalogEntry(
                id="2",
                title="总结：怎样成为「大人物」",
                url="https://www.dedao.cn/2",
                order=2,
                section_topic="《内部掌控，外部影响》(14讲)",
            ),
        ]
        assigned, unassigned = assign_topics(entries)
        self.assertEqual([entry.assigned_topic for entry in assigned], ["内部掌控，外部影响", "内部掌控，外部影响"])
        self.assertEqual(unassigned, [])

    def test_assign_topics_prefers_section_over_embedded_book_title(self) -> None:
        entries = [
            CatalogEntry(
                id="1",
                title="《后资本主义生活》给AI时代的启发",
                url="https://www.dedao.cn/1",
                order=1,
                section_topic="非专业知识·强化学习(34讲)",
            ),
        ]
        assigned, unassigned = assign_topics(entries)
        self.assertEqual([entry.assigned_topic for entry in assigned], ["非专业知识·强化学习"])
        self.assertEqual(unassigned, [])

    def test_catalog_entry_keeps_extra_fields(self) -> None:
        entry = CatalogEntry(
            id="1",
            title="中年最大的危机是社交封闭",
            url="https://www.dedao.cn/1",
            order=198,
            source_index=205,
            section_topic="非专业知识·价值对齐(18讲)",
        )
        cloned = CatalogEntry.from_dict(entry.to_dict())
        self.assertEqual(cloned.source_index, 205)
        self.assertEqual(cloned.section_topic, "非专业知识·价值对齐(18讲)")

    def test_unassigned_before_first_topic(self) -> None:
        entries = [
            CatalogEntry(id="1", title="问答：课程总说", url="https://www.dedao.cn/1", order=1),
            CatalogEntry(id="2", title="《再看一眼》1：习惯化和去习惯化", url="https://www.dedao.cn/2", order=2),
        ]
        assigned, unassigned = assign_topics(entries)
        self.assertEqual(len(assigned), 1)
        self.assertEqual(len(unassigned), 1)
        self.assertIsNone(unassigned[0].assigned_topic)

    def test_special_release_items_stay_unassigned_except_season_ending(self) -> None:
        entries = [
            CatalogEntry(
                id="1",
                title="特别放送：精英日课1-4季书单及中文书对照表",
                url="https://www.dedao.cn/1",
                order=1,
                section_topic="特别放送(5讲)",
            ),
            CatalogEntry(
                id="2",
                title="第五季结束语：智慧和智能",
                url="https://www.dedao.cn/2",
                order=2,
                section_topic="特别放送(5讲)",
            ),
        ]
        assigned, unassigned = assign_topics(entries)
        self.assertEqual([entry.assigned_topic for entry in assigned], ["第五季结束语"])
        self.assertEqual(len(unassigned), 1)

    def test_ordered_topic_names(self) -> None:
        entries = [
            CatalogEntry(id="1", title="《再看一眼》1：习惯化和去习惯化", url="https://www.dedao.cn/1", order=10, assigned_topic="再看一眼"),
            CatalogEntry(id="2", title="《最小阻力之路》1：开篇", url="https://www.dedao.cn/2", order=20, assigned_topic="最小阻力之路"),
            CatalogEntry(id="3", title="问答：补充", url="https://www.dedao.cn/3", order=11, assigned_topic="再看一眼"),
        ]
        self.assertEqual(ordered_topic_names(entries), ["再看一眼", "最小阻力之路"])

    def test_select_topic_names_after_topic(self) -> None:
        entries = [
            CatalogEntry(id="1", title="《再看一眼》1：习惯化和去习惯化", url="https://www.dedao.cn/1", order=1, assigned_topic="再看一眼"),
            CatalogEntry(id="2", title="《最小阻力之路》1：开篇", url="https://www.dedao.cn/2", order=9, assigned_topic="最小阻力之路"),
            CatalogEntry(id="3", title="《助推》1：开篇", url="https://www.dedao.cn/3", order=17, assigned_topic="助推"),
        ]
        self.assertEqual(
            select_topic_names(entries, start_after_topic="再看一眼", topic_limit=2),
            ["最小阻力之路", "助推"],
        )

    def test_select_topic_names_range(self) -> None:
        entries = [
            CatalogEntry(id="0", title="发刊词：非专业知识", url="https://www.dedao.cn/0", order=1, assigned_topic="发刊词"),
            CatalogEntry(id="1", title="《再看一眼》1：习惯化和去习惯化", url="https://www.dedao.cn/1", order=2, assigned_topic="再看一眼"),
            CatalogEntry(id="2", title="《稀缺大脑》1：开篇", url="https://www.dedao.cn/2", order=10, assigned_topic="稀缺大脑"),
            CatalogEntry(id="3", title="《心智重构》1：开篇", url="https://www.dedao.cn/3", order=18, assigned_topic="心智重构"),
        ]
        self.assertEqual(
            select_topic_names(entries, start_topic="发刊词", end_topic="稀缺大脑"),
            ["发刊词", "再看一眼", "稀缺大脑"],
        )

    def test_select_topic_names_validates_unknown_topic(self) -> None:
        entries = [
            CatalogEntry(id="1", title="《再看一眼》1：习惯化和去习惯化", url="https://www.dedao.cn/1", order=1, assigned_topic="再看一眼"),
        ]
        with self.assertRaises(ValueError):
            select_topic_names(entries, start_after_topic="不存在的专题", topic_limit=2)

    def test_select_topic_names_validates_invalid_range(self) -> None:
        entries = [
            CatalogEntry(id="1", title="《再看一眼》1：习惯化和去习惯化", url="https://www.dedao.cn/1", order=1, assigned_topic="再看一眼"),
            CatalogEntry(id="2", title="《稀缺大脑》1：开篇", url="https://www.dedao.cn/2", order=9, assigned_topic="稀缺大脑"),
        ]
        with self.assertRaises(ValueError):
            select_topic_names(entries, start_topic="稀缺大脑", end_topic="再看一眼")


if __name__ == "__main__":
    unittest.main()
