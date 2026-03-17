from __future__ import annotations

import streamlit as st

from agent_types import ChatMessage
from chat_state import (
    append_assistant_message,
    append_user_message,
    ensure_chat_session,
    get_history,
    reset_chat_session,
    update_active_filters,
)
from preflight import run_preflight
from rag_pipeline import ask, sources
from rag_answer import llm_available


def render_assistant_metadata(message: ChatMessage, show_debug: bool) -> None:
    metadata = message.metadata or {}
    retrieval_mode = metadata.get("retrieval_mode", "")
    if retrieval_mode:
        label_map = {
            "llm_enhanced": "当前回答模式: LLM 增强回答",
            "llm_guarded": "当前回答模式: LLM 增强回答（已用本地证据纠偏）",
            "llm_error_fallback": "当前回答模式: 检索回退回答（LLM 调用失败）",
            "grounding_fallback": "当前回答模式: 检索回退回答（知识库未覆盖该概念）",
            "retrieval_fallback": "当前回答模式: 检索回退回答（LLM 未接通）",
            "retrieval_only": "当前回答模式: 纯检索回答",
        }
        st.caption(label_map.get(retrieval_mode, f"当前回答模式: {retrieval_mode}"))
    evidence = metadata.get("evidence", [])
    if evidence:
        with st.expander("查看证据", expanded=False):
            for item in evidence:
                st.markdown(
                    f"**{item['ref_id']} {item['doc_title']} / {item['section_title']}**  \n"
                    f"来源: `{item['source']}`  series: `{item['series']}`  分数: `{item['score']:.3f}`"
                )
                st.write(item["snippet"])
                if item.get("source_url"):
                    st.write(f"来源链接: {item['source_url']}")
                st.divider()
    if show_debug:
        with st.expander("调试信息", expanded=False):
            st.json(metadata.get("debug", {}))
            st.caption(f"standalone_query: {metadata.get('standalone_query', '')}")
            st.caption(f"retrieval_mode: {metadata.get('retrieval_mode', '')} | confidence: {metadata.get('confidence', '')}")


def main() -> None:
    st.set_page_config(page_title="PersonalKnowledgeAI Agent", layout="wide")
    st.title("PersonalKnowledgeAI Agent")

    status = run_preflight()
    for warning in status.warnings:
        st.warning(warning)
    if not status.ready:
        st.error("当前知识库未就绪，请先在项目目录运行 `python src/main.py build-all`。")
        for issue in status.issues:
            st.write(f"- {issue}")
        return

    source_catalog = sources()
    if not source_catalog["source_count"] and not status.stats.get("chunks"):
        st.error("还没有可用的 chunks.jsonl，请先完成构建。")
        return

    ensure_chat_session(st.session_state)
    sources_list = source_catalog["sources"]
    categories = source_catalog["primary_categories"]
    topic_tags = source_catalog["topic_tags"]
    attribute_tags = source_catalog["attribute_tags"]
    series_list = source_catalog["series"]

    with st.sidebar:
        st.subheader("知识范围")
        source_filter = st.selectbox("来源", ["全部"] + sources_list)
        series_filter = st.selectbox("series", ["全部"] + series_list)
        primary_filter = st.selectbox("一级标题", ["全部"] + categories)
        topic_filter = st.selectbox("主题标签", ["全部"] + topic_tags)
        attribute_filter = st.selectbox("属性标签", ["全部"] + attribute_tags)
        mode = st.radio("模式", ["纯检索回答", "LLM 增强回答"])
        top_k = st.slider("top_k", min_value=3, max_value=10, value=6)
        alpha = st.slider("alpha", min_value=0.0, max_value=1.0, value=0.45, step=0.05)
        show_debug = st.toggle("show_debug", value=False)
        if st.button("新建会话", use_container_width=True):
            reset_chat_session(st.session_state)
            st.rerun()

    filters = {
        "source": None if source_filter == "全部" else source_filter,
        "series": None if series_filter == "全部" else series_filter,
        "primary_category": None if primary_filter == "全部" else primary_filter,
        "topic_tags": None if topic_filter == "全部" else topic_filter,
        "attribute_tags": None if attribute_filter == "全部" else attribute_filter,
    }
    update_active_filters(st.session_state, filters)

    left, right = st.columns([3, 1])
    with right:
        st.metric("documents", status.stats.get("documents", 0))
        st.metric("chunks", status.stats.get("chunks", 0))
        st.metric("review_queue", status.stats.get("review_queue", 0))
        if mode == "LLM 增强回答":
            if llm_available():
                st.success("LLM 已配置，当前使用增强模式。")
            else:
                st.error("你选择了 LLM 增强回答，但当前并没有真正接通 LLM，回答会回退到检索模式。")

    with left:
        history = get_history(st.session_state)
        if not history:
            st.info("输入问题后开始检索问答。支持连续追问和来源过滤。")
        for message in history:
            with st.chat_message("user" if message.role == "user" else "assistant"):
                st.markdown(message.content)
                if message.role == "assistant":
                    render_assistant_metadata(message, show_debug)

    user_query = st.chat_input("输入你的问题，例如：拖延症的本质是什么？")
    if not user_query:
        return

    append_user_message(st.session_state, user_query)
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        with st.spinner("正在检索并生成回答..."):
            response = ask(
                query=user_query,
                filters=filters,
                top_k=top_k,
                alpha=alpha,
                prefer_llm=(mode == "LLM 增强回答"),
                history=history,
            )
        st.markdown(response.answer_markdown)
        render_assistant_metadata(ChatMessage.create(role="assistant", content=response.answer_markdown, metadata=response.to_dict()), show_debug)

    append_assistant_message(st.session_state, response)


if __name__ == "__main__":
    main()
