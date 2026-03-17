from __future__ import annotations

import json
import os
import subprocess

import requests
from requests import RequestException

from agent_types import ChatMessage
from settings import OPENAI_API_KEY_ENV, OPENAI_BASE_URL_ENV, OPENAI_MODEL_ENV, RUNTIME


def llm_available() -> bool:
    return all(os.getenv(name) for name in [OPENAI_API_KEY_ENV, OPENAI_BASE_URL_ENV, OPENAI_MODEL_ENV])


def describe_generation_runtime() -> dict:
    base_url = os.getenv(OPENAI_BASE_URL_ENV, "").strip()
    model_name = os.getenv(OPENAI_MODEL_ENV, "").strip()
    provider = "openai-compatible"
    if "dashscope" in base_url.lower():
        provider = "dashscope"
    elif "siliconflow" in base_url.lower():
        provider = "siliconflow"
    return {
        "configured": llm_available(),
        "provider": provider,
        "base_url": base_url,
        "model_name": model_name,
        "enabled": bool(RUNTIME.generation.enabled),
    }


def _curl_chat(payload: dict) -> str:
    result = subprocess.run(
        [
            "curl",
            "--silent",
            "--show-error",
            "--request",
            "POST",
            "--url",
            os.getenv(OPENAI_BASE_URL_ENV).rstrip("/") + "/chat/completions",
            "--header",
            f"Authorization: Bearer {os.getenv(OPENAI_API_KEY_ENV)}",
            "--header",
            "Content-Type: application/json",
            "--data",
            json.dumps(payload, ensure_ascii=False),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    return data["choices"][0]["message"]["content"]


def _post_chat(messages: list[dict], temperature: float = 0.1) -> str:
    payload = {
        "model": os.getenv(OPENAI_MODEL_ENV),
        "messages": messages,
        "temperature": temperature,
    }
    try:
        response = requests.post(
            os.getenv(OPENAI_BASE_URL_ENV).rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv(OPENAI_API_KEY_ENV)}", "Content-Type": "application/json"},
            json={**payload, "response_format": {"type": "json_object"}},
            timeout=90,
        )
        if response.status_code >= 400:
            retry = requests.post(
                os.getenv(OPENAI_BASE_URL_ENV).rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv(OPENAI_API_KEY_ENV)}", "Content-Type": "application/json"},
                json=payload,
                timeout=90,
            )
            retry.raise_for_status()
            return retry.json()["choices"][0]["message"]["content"]
        return response.json()["choices"][0]["message"]["content"]
    except (RequestException, json.JSONDecodeError, KeyError, ValueError, subprocess.SubprocessError):
        return _curl_chat(payload)


def chat_text(messages: list[dict], temperature: float = 0.1) -> str:
    return _post_chat(messages, temperature=temperature)


def _parse_json_response(raw_text: str) -> dict:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = [line for line in stripped.splitlines() if not line.strip().startswith("```")]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


def chat_json(messages: list[dict], temperature: float = 0.1) -> dict:
    return _parse_json_response(chat_text(messages, temperature=temperature))


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "是", "需要"}:
            return True
        if normalized in {"false", "no", "0", "否", "不需要"}:
            return False
    return bool(value)


def rewrite_query_with_llm(history: list[ChatMessage], user_query: str) -> str:
    if not llm_available():
        return user_query
    recent_messages = history[-4:]
    conversation = []
    for message in recent_messages:
        conversation.append(f"{message.role}: {message.content}")
    prompt = (
        "请把最后一个用户问题改写成适合检索的独立问题。"
        "不要回答问题，不要补充事实。"
        "只输出 JSON，格式为 {\"standalone_query\": \"...\"}。\n\n"
        f"对话历史:\n{chr(10).join(conversation)}\n"
        f"user: {user_query}"
    )
    try:
        payload = chat_json([{"role": "user", "content": prompt}], temperature=0.0)
        return payload.get("standalone_query") or user_query
    except Exception:
        return user_query


def generate_answer(
    query: str,
    evidence: list,
    history: list[ChatMessage] | None = None,
    standalone_query: str | None = None,
    guidance: str | None = None,
) -> dict:
    if not llm_available():
        raise RuntimeError("OpenAI-compatible API is not configured.")
    context_parts = []
    for index, item in enumerate(evidence, start=1):
        context_parts.append(
            f"[{index}] 标题: {item.doc_title} / {item.section_title}\n"
            f"来源: {item.source_url or item.chunk_id}\n"
            f"内容: {item.full_text or item.snippet}"
        )
    history_text = ""
    if history:
        history_text = "\n".join(f"{item.role}: {item.content}" for item in history[-4:])
    prompt = (
        "你是一个严格受证据约束的中文知识库问答助手。"
        "只能根据提供材料回答，不能补充材料外事实。"
        "先直接回答用户问题，再给简短展开。"
        "优先使用最直接回答问题的材料，不要被次相关材料带偏。"
        "如果材料采用分层分析、递进论证或多层解释，请概括作者最终倾向的较深层解释。"
        "如果材料明确指出前几层解释只是表层、后面才是更深层原因，你必须把这个层次关系写出来。"
        "不要因为材料没有直接出现'本质就是'这样的字面句子，就机械地回答材料不足。"
        "允许你在不新增事实的前提下，用自己的话压缩和转述证据。"
        "每个关键结论都必须带 [1] [2] 这样的引用编号。"
        "如果材料不足，请明确说明“现有材料不足以确定”。"
        "只输出 JSON，字段固定为 answer, citations, confidence, need_clarification。\n\n"
        f"用户原问题: {query}\n"
        f"检索问题: {standalone_query or query}\n"
        f"最近对话:\n{history_text}\n\n"
        f"提炼线索:\n{guidance or '无'}\n\n"
        f"材料:\n{chr(10).join(context_parts)}"
    )
    raw_text = chat_text([{"role": "user", "content": prompt}], temperature=0.1)
    payload = _parse_json_response(raw_text)
    answer = payload.get("answer", "").strip() or "现有材料不足以确定。"
    if "[" not in answer and evidence:
        refs = " ".join(f"[{index}]" for index in range(1, min(2, len(evidence)) + 1))
        answer = f"{answer}\n\n证据引用：{refs}"
    return {
        "answer_markdown": answer,
        "citations": payload.get("citations", []),
        "confidence": payload.get("confidence", "medium"),
        "need_clarification": _coerce_bool(payload.get("need_clarification", False)),
        "raw_model_output": raw_text,
        "standalone_query": standalone_query or query,
    }
