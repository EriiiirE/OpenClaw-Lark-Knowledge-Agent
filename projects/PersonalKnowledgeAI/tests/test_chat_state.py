from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_types import AgentResponse, EvidenceItem
from chat_state import append_assistant_message, append_user_message, ensure_chat_session, reset_chat_session, update_active_filters


class ChatStateTests(unittest.TestCase):
    def test_filters_persist_within_session(self):
        state = {}
        session = ensure_chat_session(state)
        self.assertEqual(len(session.messages), 0)
        update_active_filters(state, {"source": "jingyingrike", "series": None, "primary_category": None, "topic_tags": None, "attribute_tags": None})
        append_user_message(state, "B选项讲了什么")
        response = AgentResponse(
            answer_markdown="结论：[1]",
            evidence=[
                EvidenceItem(
                    ref_id="[1]",
                    chunk_id="chunk_1",
                    doc_title="B 选项",
                    section_title="第一部分",
                    source="jingyingrike",
                    series="精英日课第一季",
                    source_url="https://example.com",
                    snippet="snippet",
                    score=0.9,
                    full_text="full_text",
                )
            ],
            standalone_query="B选项讲了什么",
            retrieval_mode="retrieval_only",
            confidence="high",
            need_clarification=False,
        )
        append_assistant_message(state, response)
        self.assertEqual(state["chat_session"].active_filters["source"], "jingyingrike")
        self.assertEqual(len(state["chat_session"].messages), 2)

    def test_reset_chat_session(self):
        state = {}
        append_user_message(state, "test")
        old_session_id = state["chat_session"].session_id
        new_session = reset_chat_session(state)
        self.assertNotEqual(old_session_id, new_session.session_id)
        self.assertEqual(new_session.messages, [])


if __name__ == "__main__":
    unittest.main()
