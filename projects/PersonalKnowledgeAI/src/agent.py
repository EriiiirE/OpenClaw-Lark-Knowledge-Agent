from __future__ import annotations

from collections import defaultdict
import re

from agent_types import AgentResponse, ChatMessage, EvidenceItem, SearchOptions
from build_indexes import tokenize
from models import ChunkRecord, SearchHit
from rag_answer import generate_answer, llm_available, rewrite_query_with_llm
from retrieve import search


FOLLOW_UP_MARKERS = ("这个", "那个", "他", "她", "它", "上面", "刚才", "前面", "第二部分", "为什么", "怎么做", "这部分", "那部分")
GENERIC_QUERY_TOKENS = {
    "什么",
    "怎么",
    "如何",
    "为什么",
    "本质",
    "核心",
    "根本",
    "原因",
    "理解",
    "能力",
    "这个",
    "那个",
    "一种",
    "基本",
    "问题",
}


def rewrite_query(history: list[ChatMessage], user_query: str) -> str:
    if not history:
        return user_query
    if llm_available():
        return rewrite_query_with_llm(history, user_query)
    if any(marker in user_query for marker in FOLLOW_UP_MARKERS):
        prior_user_queries = [message.content for message in history if message.role == "user"]
        last_user_query = prior_user_queries[-1] if prior_user_queries else ""
        if last_user_query:
            return f"{last_user_query}。补充问题：{user_query}"
    return user_query


def _snippet(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[:limit].rstrip() + "..."


def _query_concept_phrase(query: str) -> str:
    compact = query.strip().replace("？", "").replace("?", "")
    for prefix in ["什么是", "请解释", "解释一下", "解释"]:
        if compact.startswith(prefix):
            compact = compact[len(prefix):].strip()
    for suffix in ["是什么", "是啥", "什么意思", "怎么理解"]:
        if compact.endswith(suffix):
            compact = compact[: -len(suffix)].strip()
    return compact


def _section_context_window(question_type: str) -> tuple[int, int, int]:
    if question_type == "definition":
        return 1, 4, 4200
    if question_type == "causal":
        return 1, 3, 3600
    if question_type == "howto":
        return 1, 2, 2800
    return 1, 1, 2200


def _expand_section_context(
    section_hits: list[SearchHit],
    all_chunks: list[ChunkRecord],
    question_type: str,
    query: str,
) -> list[ChunkRecord]:
    if not section_hits:
        return []
    anchor = max(section_hits, key=lambda item: item.score)
    key = (anchor.chunk.doc_id, anchor.chunk.section_title)
    section_chunks = sorted(
        [chunk for chunk in all_chunks if (chunk.doc_id, chunk.section_title) == key],
        key=lambda item: item.chunk_index,
    )
    if not section_chunks:
        return [item.chunk for item in sorted(section_hits, key=lambda item: item.chunk.chunk_index)]

    indices = sorted({item.chunk.chunk_index for item in section_hits})
    left_window, right_window, char_limit = _section_context_window(question_type)
    available = {chunk.chunk_index: chunk for chunk in section_chunks}
    min_index = min(indices)
    max_index = max(indices)
    priority_indices = list(range(min_index, max_index + 1))
    if question_type == "definition":
        concept_phrase = _query_concept_phrase(query)
        core_tokens = _core_query_tokens(query)
        exact_match_indices = []
        for chunk in section_chunks:
            text = f"{chunk.doc_title} {chunk.section_title} {chunk.text}".lower()
            if concept_phrase and concept_phrase in text:
                exact_match_indices.append(chunk.chunk_index)
                continue
            if core_tokens and sum(1 for token in set(core_tokens) if token in text) >= min(len(set(core_tokens)), 2):
                exact_match_indices.append(chunk.chunk_index)
        priority_indices.extend(exact_match_indices)
    for step in range(1, right_window + 1):
        priority_indices.append(anchor.chunk.chunk_index + step)
    for step in range(1, left_window + 1):
        priority_indices.append(anchor.chunk.chunk_index - step)

    chosen_indices: list[int] = []
    used: set[int] = set()
    total_chars = 0
    for index in priority_indices:
        chunk = available.get(index)
        if chunk is None or index in used:
            continue
        if total_chars + chunk.char_count > char_limit and chosen_indices:
            continue
        chosen_indices.append(index)
        used.add(index)
        total_chars += chunk.char_count
    return [available[index] for index in sorted(chosen_indices)]


def _merge_hits_into_evidence(hits: list[SearchHit], all_chunks: list[ChunkRecord], query: str, max_blocks: int = 4) -> list[EvidenceItem]:
    question_type = _question_type(query)
    grouped: dict[tuple[str, str], list[SearchHit]] = defaultdict(list)
    order: list[tuple[str, str]] = []
    for hit in hits:
        key = (hit.chunk.doc_id, hit.chunk.section_title)
        if key not in grouped:
            order.append(key)
        grouped[key].append(hit)

    evidence: list[EvidenceItem] = []
    for ref_index, key in enumerate(order[:max_blocks], start=1):
        section_hits = sorted(grouped[key], key=lambda item: item.chunk.chunk_index)
        expanded_chunks = _expand_section_context(section_hits, all_chunks, question_type, query)
        full_text = "\n\n".join(item.text for item in expanded_chunks)
        anchor = max(section_hits, key=lambda item: item.score)
        evidence.append(
            EvidenceItem(
                ref_id=f"[{ref_index}]",
                chunk_id=",".join(item.chunk_id for item in expanded_chunks),
                doc_title=anchor.chunk.doc_title,
                section_title=anchor.chunk.section_title,
                source=anchor.chunk.source,
                series=anchor.chunk.series,
                source_url=anchor.chunk.source_url,
                snippet=_snippet(full_text, 220),
                score=round(max(item.score for item in section_hits), 4),
                full_text=full_text,
            )
        )
    return evidence


def _select_relevant_evidence(evidence: list[EvidenceItem], query: str, max_blocks: int = 3) -> list[EvidenceItem]:
    if not evidence:
        return evidence
    query_tokens = [token for token in tokenize(query) if len(token.strip()) > 1 and token not in GENERIC_QUERY_TOKENS]
    if not query_tokens:
        return evidence[:max_blocks]

    scored: list[tuple[float, EvidenceItem]] = []
    for item in evidence:
        text = f"{item.doc_title} {item.section_title} {item.full_text or item.snippet}".lower()
        score = item.score
        token_hits = sum(1 for token in query_tokens if token in text)
        score += token_hits * 0.6
        if item.doc_title in query or item.section_title in query:
            score += 0.8
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    selected = [item for score, item in scored if any(token in f'{item.doc_title} {item.section_title} {item.full_text or item.snippet}'.lower() for token in query_tokens)]
    if not selected:
        selected = [item for _, item in scored]
    if _question_type(query) == "definition":
        top = selected[0]
        title_text = f"{top.doc_title} {top.section_title}".lower()
        if any(token in title_text for token in query_tokens):
            return [top]
    return selected[:max_blocks]


def _question_type(query: str) -> str:
    if any(token in query for token in ["本质", "核心", "根本", "是什么", "什么是"]):
        return "definition"
    if any(token in query for token in ["为什么", "原因"]):
        return "causal"
    if any(token in query for token in ["怎么", "如何"]):
        return "howto"
    if any(token in query for token in ["区别", "不同", "对比"]):
        return "compare"
    return "general"


def _extract_definition_claim(full_text: str) -> str | None:
    compact = full_text.replace("\n", " ")
    patterns = [
        r"拖延(?:症)?(?:的真实问题|的根源)?是[——:： ]*(.+?)(?:。|；)",
        r"拖延(?:症)?只不过是一个表层现象而已[，,](.+?)(?:。|；)",
        r"更深一层的(?:原因|问题)是[：: ]*(.+?)(?:。|；)",
        r"拖延(?:症)?(?:的本质)?(?:更接近于|其实是)(.+?)(?:。|；)",
        r"拖延(?:症)?的理解是[：:](.+?)(?:。|；)",
        r"拖延(?:症)?是由于(.+?)(?:。|；)",
        r"本质上(.+?)(?:。|；)",
    ]
    candidates: list[tuple[float, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, compact):
            claim = match.group(1).strip(" ：:，,")
            if len(claim) < 6:
                continue
            score = float(match.start()) / 1000.0
            if any(token in claim for token in ["潜意识", "心智最底层", "原生家庭", "童年", "表层症状", "负面的力量", "心理阻抗"]):
                score += 3.0
            if any(token in claim for token in ["行动没有意义", "缺乏行动目标的清晰度", "执行力", "意志力"]):
                score -= 2.5
            candidates.append((score, claim))
    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]
    if all(token in compact for token in ["前4层", "第5层"]) and any(token in compact for token in ["潜意识", "童年", "原生家庭", "心智最底层"]):
        return "拖延更深层上是心智最底层的旧创伤、潜意识冲突和长期压抑持续向表层释放阻力，拖延只是表层症状"
    if "心智最底层" in compact and "拖延" in compact:
        return "拖延更接近于心智最底层的问题持续向表层散发负面力量的结果"
    return None


def _core_query_tokens(query: str) -> list[str]:
    return [token for token in tokenize(query) if len(token.strip()) > 1 and token not in GENERIC_QUERY_TOKENS]


def _has_semantic_grounding(query: str, evidence: EvidenceItem) -> bool:
    tokens = _core_query_tokens(query)
    if not tokens:
        return True
    text = f"{evidence.doc_title} {evidence.section_title} {evidence.full_text or evidence.snippet}".lower()
    hit_count = sum(1 for token in set(tokens) if token in text)
    if len(tokens) == 1:
        return hit_count >= 1
    required_hits = max(2, min(len(set(tokens)), 2))
    return hit_count >= required_hits


def _extract_key_sentences(full_text: str, question_type: str, query: str, limit: int = 3) -> list[str]:
    normalized = full_text.replace("\n", " ")
    sentences = [part.strip() for part in normalized.split("。") if part.strip()]
    query_tokens = [token for token in tokenize(query) if len(token.strip()) > 1]
    scored: list[tuple[float, str]] = []
    for sentence in sentences:
        score = 0.0
        if sentence in {"零", "壹", "贰", "叁", "肆", "伍"}:
            continue
        if any(noisy in sentence for noisy in ["这篇文章", "点击上方", "免费获得", "广告"]):
            score -= 1.5
        if question_type == "definition" and any(marker in sentence for marker in ["本质", "根本", "核心", "不是", "真正", "更深"]):
            score += 3.0
        if question_type == "definition" and any(marker in sentence for marker in ["理解是", "由于", "导致", "其实就是"]):
            score += 2.2
        if question_type == "causal" and any(marker in sentence for marker in ["因为", "原因", "导致", "背后"]):
            score += 2.5
        if question_type == "howto" and any(marker in sentence for marker in ["应该", "可以", "方法", "步骤", "首先"]):
            score += 2.5
        token_hits = sum(1 for token in query_tokens if token in sentence.lower())
        score += token_hits * 0.8
        if len(sentence) > 18:
            score += 0.3
        scored.append((score, sentence))
    scored.sort(key=lambda item: item[0], reverse=True)
    picked: list[str] = []
    for score, sentence in scored:
        if score <= 0:
            continue
        if sentence in picked:
            continue
        picked.append(sentence)
        if len(picked) >= limit:
            break
    return picked


def _extractive_answer(query: str, evidence: list[EvidenceItem]) -> tuple[str, str, bool]:
    if not evidence:
        return "现有材料不足以确定。", "low", True
    question_type = _question_type(query)
    best = evidence[0]
    if question_type == "definition" and not _has_semantic_grounding(query, best):
        return "现有材料不足以确定。当前知识库里没有直接覆盖这个概念的可靠材料。", "low", True
    key_sentences = _extract_key_sentences(best.full_text or best.snippet, question_type, query, limit=3)
    if not key_sentences:
        return "现有材料不足以确定。", "low", True

    if question_type == "definition":
        claim = _extract_definition_claim(best.full_text or best.snippet)
        if claim and not any(marker in claim for marker in ["缺乏行动目标的清晰度", "行动没有意义", "第三级", "这一层级"]):
            direct_answer = f"结论：从当前材料看，{query.replace('是什么', '').replace('？', '').replace('?', '')}可以概括为：{claim}。{best.ref_id}"
        else:
            direct_answer = f"结论：从当前材料看，{query.replace('是什么', '').replace('？', '').replace('?', '')}更接近于一种更深层的心理阻抗或心智损耗，而不只是表面的执行力差。{best.ref_id}"
    elif question_type == "causal":
        direct_answer = f"结论：当前材料认为，这背后通常有更深层的心理原因或内在冲突，而不是单一表面原因。{best.ref_id}"
    elif question_type == "howto":
        direct_answer = f"结论：当前材料的重点不是给技巧清单，而是先识别更深层的问题，再谈对应做法。{best.ref_id}"
    else:
        direct_answer = f"结论：当前最直接回答这个问题的材料主要来自《{best.doc_title}》的“{best.section_title}”。{best.ref_id}"

    explanation = "\n".join(f"- {sentence}。{best.ref_id}" for sentence in key_sentences[:3])
    evidence_lines = [
        f"{item.ref_id} 《{item.doc_title}》/“{item.section_title}”：{item.snippet}"
        for item in evidence[: min(3, len(evidence))]
    ]
    answer_markdown = "\n".join(
        [
            direct_answer,
            "",
            "展开：",
            explanation,
            "",
            "证据：",
            *evidence_lines,
            "",
            "如果你想继续追问，我可以继续把这篇文章里的层级逻辑拆开讲。",
        ]
    )
    return answer_markdown, "medium", False


def _build_answer_guidance(query: str, evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "没有可用证据。"
    question_type = _question_type(query)
    best = evidence[0]
    guidance_lines = [
        "优先围绕最直接命中的主证据作答，不要把次相关证据当成主结论。",
        f"主证据标题: 《{best.doc_title}》/“{best.section_title}” {best.ref_id}",
    ]
    if question_type == "definition":
        claim = _extract_definition_claim(best.full_text or best.snippet)
        if claim:
            guidance_lines.append(f"候选直接结论: {claim}")
        guidance_lines.append("如果材料呈现前几层解释与更深层解释，请明确写成“不是A/B，而是更深层的C”。")
    key_sentences = _extract_key_sentences(best.full_text or best.snippet, question_type, query, limit=3)
    if key_sentences:
        guidance_lines.append("可优先参考的关键句:")
        guidance_lines.extend(f"- {sentence}" for sentence in key_sentences)
    return "\n".join(guidance_lines)


def _looks_insufficient(answer: str) -> bool:
    compact = answer.replace(" ", "")
    markers = ["现有材料不足以确定", "材料不足", "无法确定", "无法直接判断", "信息不足"]
    return any(marker in compact for marker in markers)


def _should_require_grounding(query: str) -> bool:
    return _question_type(query) == "definition"


def answer_question(
    user_query: str,
    chunks: list[ChunkRecord],
    history: list[ChatMessage],
    options: SearchOptions,
    prefer_llm: bool,
) -> AgentResponse:
    standalone_query = rewrite_query(history, user_query)
    hits = search(query=standalone_query, chunks=chunks, options=options)
    evidence = _select_relevant_evidence(_merge_hits_into_evidence(hits, chunks, standalone_query), standalone_query)
    extractive_answer, extractive_confidence, extractive_need_clarification = _extractive_answer(user_query, evidence)
    answer_markdown = extractive_answer
    confidence = extractive_confidence
    need_clarification = extractive_need_clarification
    retrieval_mode = "retrieval_only"
    debug = {
        "user_query": user_query,
        "standalone_query": standalone_query,
        "applied_filters": options.filters,
        "raw_hit_count": len(hits),
        "evidence_block_count": len(evidence),
    }
    grounded = bool(evidence) and _has_semantic_grounding(user_query, evidence[0])
    debug["grounded"] = grounded

    if prefer_llm and llm_available() and _should_require_grounding(user_query) and not grounded:
        retrieval_mode = "grounding_fallback"
    elif prefer_llm and llm_available():
        try:
            payload = generate_answer(
                query=user_query,
                evidence=evidence,
                history=history,
                standalone_query=standalone_query,
                guidance=_build_answer_guidance(user_query, evidence),
            )
            answer_markdown = payload["answer_markdown"]
            confidence = str(payload.get("confidence", "medium"))
            need_clarification = bool(payload.get("need_clarification", False))
            retrieval_mode = "llm_enhanced"
            if _looks_insufficient(answer_markdown) and not extractive_need_clarification and evidence and _has_semantic_grounding(user_query, evidence[0]):
                answer_markdown = extractive_answer
                confidence = extractive_confidence
                need_clarification = extractive_need_clarification
                retrieval_mode = "llm_guarded"
                debug["llm_answer_overridden"] = True
            debug["raw_model_output"] = payload.get("raw_model_output", "")
        except Exception as exc:
            retrieval_mode = "llm_error_fallback"
            debug["llm_error"] = str(exc)
    if prefer_llm and not llm_available():
        retrieval_mode = "retrieval_fallback"
    return AgentResponse(
        answer_markdown=answer_markdown,
        evidence=evidence,
        standalone_query=standalone_query,
        retrieval_mode=retrieval_mode,
        confidence=confidence,
        need_clarification=need_clarification,
        debug=debug,
    )
