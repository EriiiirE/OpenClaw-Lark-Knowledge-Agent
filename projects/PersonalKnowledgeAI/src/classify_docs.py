from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Any

import requests

from models import DocumentRecord, ReviewCandidate, ReviewItem
from settings import OPENAI_API_KEY_ENV, OPENAI_BASE_URL_ENV, OPENAI_MODEL_ENV
from taxonomy import deduplicate_topic_labels, group_for_topic_tag, load_taxonomy, validate_attribute_labels, validate_primary_label, validate_topic_labels
from utils_markdown import clean_text, split_sentences


def _weighted_count(text: str, keyword: str) -> int:
    return text.lower().count(keyword.lower())


def build_doc_text(doc: DocumentRecord) -> str:
    parts = [doc.title]
    for section in doc.sections:
        parts.append(section.title)
        parts.append(section.text)
    return "\n".join(parts)


def summarize_doc(doc: DocumentRecord, candidate_keywords: list[str]) -> str:
    text = build_doc_text(doc)
    sentences = split_sentences(text)
    if not sentences:
        return doc.title
    scored: list[tuple[float, str]] = []
    for index, sentence in enumerate(sentences[:8]):
        score = max(0.0, 1.4 - (index * 0.1))
        lowered = sentence.lower()
        for keyword in candidate_keywords:
            if keyword.lower() in lowered:
                score += 0.8
        scored.append((score, sentence))
    scored.sort(key=lambda item: item[0], reverse=True)
    summary = scored[0][1]
    return summary[:80].rstrip("，,；; ") + ("..." if len(summary) > 80 else "")


def score_primary_categories(doc: DocumentRecord, taxonomy) -> dict[str, float]:
    hints = taxonomy.keyword_hints["primary_categories"]
    path_text = doc.file_path
    title_text = " ".join([doc.title] + [section.title for section in doc.sections])
    body_text = build_doc_text(doc)
    scores = defaultdict(float)
    for label in taxonomy.primary_categories:
        info = hints.get(label, {})
        for keyword in info.get("path", []):
            scores[label] += _weighted_count(path_text, keyword) * 0.7
        for keyword in info.get("title", []):
            scores[label] += _weighted_count(title_text, keyword) * 1.5
        for keyword in info.get("body", []):
            scores[label] += _weighted_count(body_text, keyword) * 0.4
    total = sum(scores.values()) or 1.0
    return {label: value / total for label, value in scores.items()}


def score_topic_tags(doc: DocumentRecord, taxonomy) -> dict[str, float]:
    hints = taxonomy.keyword_hints["topic_tags"]
    text = build_doc_text(doc)
    title_text = " ".join([doc.title] + [section.title for section in doc.sections])
    scores = defaultdict(float)
    for label in taxonomy.topic_tags:
        for keyword in hints.get(label, []):
            scores[label] += _weighted_count(title_text, keyword) * 1.2
            scores[label] += _weighted_count(text, keyword) * 0.35
    total = max(scores.values(), default=0.0) or 1.0
    return {label: value / total for label, value in scores.items() if value > 0}


def infer_attribute_tags(doc: DocumentRecord) -> list[str]:
    tags: list[str] = []
    if doc.source == "jingyingrike":
        tags.extend(["精英日课"])
    elif doc.source == "yexiu_wechat":
        tags.extend(["叶修公众号", "微信公众号"])
    else:
        tags.extend(["本地知识库", "用户资料"])
    title_text = doc.title + " " + " ".join(section.title for section in doc.sections)
    body = build_doc_text(doc)
    if "发刊词" in title_text:
        tags.append("发刊词")
    elif "问答" in title_text:
        tags.append("问答")
    elif any(marker in title_text for marker in ["总结", "结束语"]):
        tags.append("系列总结")
    elif "《" in title_text and doc.source == "jingyingrike":
        tags.append("解书")
    elif any(marker in title_text for marker in ["个案", "案例"]) or "案例" in body[:500]:
        tags.append("案例")
    else:
        if doc.source == "yexiu_wechat":
            tags.append("方法文")
        elif doc.source == "local_knowledge":
            tags.append("个人笔记")
        else:
            tags.append("主题文章")

    audience_markers = {
        "学生": ["学生", "高考", "作文", "中学", "高中", "初中"],
        "家长": ["家长", "父母", "家庭教育"],
        "职场人": ["职场", "公司", "管理", "组织", "团队"],
        "产品经理": ["产品经理", "产品", "需求"],
    }
    chosen_audience = None
    for label, markers in audience_markers.items():
        if any(marker in body or marker in title_text for marker in markers):
            chosen_audience = label
            break
    tags.append(chosen_audience or "普通读者")
    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:3]


def rule_classify(doc: DocumentRecord) -> tuple[DocumentRecord, ReviewItem | None]:
    taxonomy = load_taxonomy()
    primary_scores = score_primary_categories(doc, taxonomy)
    ranked_primary = sorted(primary_scores.items(), key=lambda item: item[1], reverse=True)
    primary_label = ranked_primary[0][0] if ranked_primary else taxonomy.primary_categories[0]
    primary_score = ranked_primary[0][1] if ranked_primary else 0.0
    second_score = ranked_primary[1][1] if len(ranked_primary) > 1 else 0.0

    topic_scores = score_topic_tags(doc, taxonomy)
    ranked_topics = sorted(topic_scores.items(), key=lambda item: item[1], reverse=True)
    topic_threshold = taxonomy.rules.get("min_topic_score", 0.18)
    topic_tags = [label for label, score in ranked_topics if score >= topic_threshold][:4]
    topic_tags = deduplicate_topic_labels(taxonomy, topic_tags)
    if len(topic_tags) < taxonomy.rules["topic_min"]:
        fallback_topics = taxonomy.topic_groups.get(primary_label, [])[: taxonomy.rules["topic_min"]]
        for tag in fallback_topics:
            if tag not in topic_tags:
                topic_tags.append(tag)
                if len(topic_tags) >= taxonomy.rules["topic_min"]:
                    break
    topic_tags = topic_tags[: taxonomy.rules["topic_max"]]

    attribute_tags = infer_attribute_tags(doc)
    summary_keywords = [primary_label] + topic_tags
    summary = summarize_doc(doc, summary_keywords)

    review_required = primary_score < taxonomy.rules["min_primary_score"] or (primary_score - second_score) < taxonomy.rules["min_primary_gap"]
    review_reason = None
    if primary_score < taxonomy.rules["min_primary_score"]:
        review_reason = "low_primary_score"
    elif (primary_score - second_score) < taxonomy.rules["min_primary_gap"]:
        review_reason = "low_primary_gap"

    updated = DocumentRecord(**{**doc.to_dict(), "sections": doc.sections})
    updated.primary_category = primary_label
    updated.topic_tags = topic_tags
    updated.attribute_tags = attribute_tags
    updated.summary = summary
    updated.review_required = review_required
    updated.review_reason = review_reason

    review_item = None
    if review_required:
        review_item = ReviewItem(
            doc_id=doc.doc_id,
            file_path=doc.file_path,
            title=doc.title,
            candidate_primary_categories=[ReviewCandidate(label, score) for label, score in ranked_primary[:3]],
            candidate_topic_tags=[ReviewCandidate(label, score) for label, score in ranked_topics[:6]],
            current_attribute_tags=attribute_tags,
            summary=summary,
            review_reason=review_reason or "manual_review",
        )
    return updated, review_item


def call_openai_compatible(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv(OPENAI_API_KEY_ENV)
    base_url = os.getenv(OPENAI_BASE_URL_ENV)
    model = os.getenv(OPENAI_MODEL_ENV)
    if not api_key or not base_url or not model:
        raise RuntimeError("OpenAI-compatible environment variables are not configured.")
    response = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": payload["messages"],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    return json.loads(content)


def llm_classify(doc: DocumentRecord) -> tuple[DocumentRecord, ReviewItem | None]:
    taxonomy = load_taxonomy()
    rule_doc, review_item = rule_classify(doc)
    prompt = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "你只能从给定 taxonomy 中选择标签，必须返回 JSON。"
                    "字段: primary_category, topic_tags, attribute_tags, summary。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title": doc.title,
                        "file_path": doc.file_path,
                        "text": build_doc_text(doc)[:8000],
                        "primary_categories": taxonomy.primary_categories,
                        "topic_tags": taxonomy.topic_tags,
                        "attribute_tags": taxonomy.attribute_tags,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    }
    try:
        result = call_openai_compatible(prompt)
    except Exception:
        return rule_doc, review_item

    primary = result.get("primary_category")
    topic_tags = result.get("topic_tags") or []
    attribute_tags = result.get("attribute_tags") or []
    summary = result.get("summary") or rule_doc.summary
    if not isinstance(topic_tags, list) or not isinstance(attribute_tags, list):
        return rule_doc, review_item
    if not validate_primary_label(taxonomy, primary):
        return rule_doc, review_item
    if not validate_topic_labels(taxonomy, topic_tags):
        return rule_doc, review_item
    if not validate_attribute_labels(taxonomy, attribute_tags):
        return rule_doc, review_item

    topic_tags = deduplicate_topic_labels(taxonomy, topic_tags)[: taxonomy.rules["topic_max"]]
    if not (taxonomy.rules["topic_min"] <= len(topic_tags) <= taxonomy.rules["topic_max"]):
        return rule_doc, review_item
    if not (taxonomy.rules["attribute_min"] <= len(attribute_tags) <= taxonomy.rules["attribute_max"]):
        return rule_doc, review_item

    updated = rule_doc
    updated.primary_category = primary
    updated.topic_tags = topic_tags
    updated.attribute_tags = attribute_tags
    updated.summary = summary[:120]

    review_required = review_item is not None
    if review_required and primary != rule_doc.primary_category:
        review_item.review_reason = review_item.review_reason or "llm_override_review"
    return updated, review_item


def classify_documents(documents: list[DocumentRecord], mode: str = "rule") -> tuple[list[DocumentRecord], list[ReviewItem]]:
    classified: list[DocumentRecord] = []
    review_items: list[ReviewItem] = []
    auto_mode = mode == "auto"
    llm_enabled = mode == "llm" or (auto_mode and all(os.getenv(name) for name in [OPENAI_API_KEY_ENV, OPENAI_BASE_URL_ENV, OPENAI_MODEL_ENV]))
    for doc in documents:
        updated, review_item = llm_classify(doc) if llm_enabled else rule_classify(doc)
        classified.append(updated)
        if review_item:
            review_items.append(review_item)
    return classified, review_items
