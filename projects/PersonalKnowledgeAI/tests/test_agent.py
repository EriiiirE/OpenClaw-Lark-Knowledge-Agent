from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent import answer_question, rewrite_query
from agent_types import ChatMessage, SearchOptions
from models import ChunkRecord, SearchHit


def build_hit(index: int = 1, text: str | None = None) -> SearchHit:
    chunk = ChunkRecord(
        chunk_id=f"chunk_{index}",
        doc_id="doc_1",
        chunk_index=index,
        source="yexiu_wechat",
        series="拖延症专题",
        doc_title="拖延症",
        section_title="底层机制",
        heading_path=["拖延症", "底层机制"],
        source_url="https://example.com",
        primary_category="成长与人生",
        topic_tags=["拖延症", "心智"],
        attribute_tags=["方法文"],
        text=text or "拖延症往往和情绪回避、即时奖励、控制感不足有关。" * 4,
        char_count=len(text or ("拖延症往往和情绪回避、即时奖励、控制感不足有关。" * 4)),
    )
    return SearchHit(
        chunk_id=chunk.chunk_id,
        score=0.86,
        bm25_score=0.75,
        vector_score=0.78,
        chunk=chunk,
        raw_bm25_score=3.2,
        raw_vector_score=0.61,
    )


class AgentTests(unittest.TestCase):
    @patch("agent.llm_available", return_value=False)
    def test_rewrite_follow_up_without_llm(self, _mock_llm_available):
        history = [ChatMessage.create(role="user", content="B选项讲了什么")]
        rewritten = rewrite_query(history, "那第二部分为什么会这样？")
        self.assertIn("B选项讲了什么", rewritten)
        self.assertIn("补充问题", rewritten)

    @patch("agent.llm_available", return_value=False)
    @patch("agent.search")
    def test_answer_question_falls_back_without_llm(self, mock_search, _mock_llm_available):
        mock_search.return_value = [build_hit(1), build_hit(2)]
        response = answer_question(
            user_query="拖延症的本质是什么",
            chunks=[],
            history=[],
            options=SearchOptions(top_k=6, alpha=0.45, filters={"source": "yexiu_wechat"}),
            prefer_llm=True,
        )
        self.assertEqual(response.retrieval_mode, "retrieval_fallback")
        self.assertFalse(response.need_clarification)
        self.assertEqual(response.evidence[0].ref_id, "[1]")
        self.assertIn("[1]", response.answer_markdown)
        self.assertIn("更接近于一种更深层的心理阻抗或心智损耗", response.answer_markdown)

    @patch("agent.search")
    def test_definition_question_expands_section_context(self, mock_search):
        chunks = [
            build_hit(
                index,
                text=(
                    "前4层的理解都无法治本。"
                    if index == 3
                    else "这些问题不解决，必然从心智最底层不断向表层散发出负面的力量形成包括拖延在内的多种问题。"
                    if index == 5
                    else f"补充材料 {index}。"
                ),
            ).chunk
            for index in range(2, 7)
        ]
        mock_search.return_value = [SearchHit(chunk_id=chunks[1].chunk_id, score=0.93, bm25_score=0.88, vector_score=0.84, chunk=chunks[1])]
        response = answer_question(
            user_query="拖延症的本质是什么",
            chunks=chunks,
            history=[],
            options=SearchOptions(top_k=6, alpha=0.45, filters={}),
            prefer_llm=False,
        )
        self.assertIn("心智最底层", response.evidence[0].full_text)
        self.assertIn("拖延更接近于心智最底层的问题持续向表层散发负面力量的结果", response.answer_markdown)

    @patch("agent.generate_answer")
    @patch("agent.llm_available")
    @patch("agent.search")
    def test_llm_insufficient_answer_is_guarded(self, mock_search, mock_llm_available, mock_generate_answer):
        chunks = [
            build_hit(
                index,
                text=(
                    "前4层的理解都无法治本。"
                    if index == 3
                    else "这些问题不解决，必然从心智最底层不断向表层散发出负面的力量形成包括拖延在内的多种问题。"
                    if index == 5
                    else f"补充材料 {index}。"
                ),
            ).chunk
            for index in range(2, 7)
        ]
        mock_search.return_value = [SearchHit(chunk_id=chunks[1].chunk_id, score=0.93, bm25_score=0.88, vector_score=0.84, chunk=chunks[1])]
        mock_llm_available.return_value = True
        mock_generate_answer.return_value = {
            "answer_markdown": "现有材料不足以确定。证据引用：[1]",
            "citations": [1],
            "confidence": "low",
            "need_clarification": True,
            "raw_model_output": "{\"answer\":\"现有材料不足以确定。证据引用：[1]\"}",
        }
        response = answer_question(
            user_query="拖延症的本质是什么",
            chunks=chunks,
            history=[],
            options=SearchOptions(top_k=6, alpha=0.45, filters={}),
            prefer_llm=True,
        )
        self.assertEqual(response.retrieval_mode, "llm_guarded")
        self.assertFalse(response.need_clarification)
        self.assertIn("心智最底层", response.answer_markdown)

    @patch("agent.search")
    def test_definition_without_grounding_returns_insufficient(self, mock_search):
        grounded_chunk = build_hit(1, text="这是一本关于社会正义谬误的书，讨论多种谬误。").chunk
        grounded_chunk.doc_title = "社会正义谬误"
        grounded_chunk.section_title = "总结：有限的正义"
        mock_search.return_value = [SearchHit(chunk_id=grounded_chunk.chunk_id, score=0.9, bm25_score=0.8, vector_score=0.7, chunk=grounded_chunk)]
        response = answer_question(
            user_query="什么是基本归因谬误",
            chunks=[grounded_chunk],
            history=[],
            options=SearchOptions(top_k=6, alpha=0.45, filters={}),
            prefer_llm=False,
        )
        self.assertTrue(response.need_clarification)
        self.assertIn("现有材料不足以确定", response.answer_markdown)

    @patch("agent.generate_answer")
    @patch("agent.llm_available", return_value=True)
    @patch("agent.search")
    def test_definition_without_grounding_skips_llm(self, mock_search, _mock_llm_available, mock_generate_answer):
        chunk = build_hit(1, text="这是一本关于社会正义谬误的书，讨论多种谬误。").chunk
        chunk.doc_title = "社会正义谬误"
        chunk.section_title = "总结：有限的正义"
        mock_search.return_value = [SearchHit(chunk_id=chunk.chunk_id, score=0.9, bm25_score=0.8, vector_score=0.7, chunk=chunk)]
        response = answer_question(
            user_query="什么是基本归因谬误",
            chunks=[chunk],
            history=[],
            options=SearchOptions(top_k=6, alpha=0.45, filters={}),
            prefer_llm=True,
        )
        mock_generate_answer.assert_not_called()
        self.assertEqual(response.retrieval_mode, "grounding_fallback")
        self.assertIn("现有材料不足以确定", response.answer_markdown)


if __name__ == "__main__":
    unittest.main()
