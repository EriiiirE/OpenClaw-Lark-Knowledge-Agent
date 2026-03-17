#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path


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
    "问题",
    "这个",
    "那个",
    "一种",
    "基本",
}

PKAI_TOKENIZER = None

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")


def _resolve_pkai_root() -> Path:
    override = os.getenv("PKAI_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[5]


def _tokenize(text: str) -> list[str]:
    if PKAI_TOKENIZER is not None:
        try:
            tokens = [token.strip().lower() for token in PKAI_TOKENIZER(text) if token.strip()]
        except Exception:
            tokens = [part.lower() for part in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text)]
    else:
        tokens = [part.lower() for part in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text)]
    return [token for token in tokens if len(token) >= 2 and token not in GENERIC_QUERY_TOKENS]


def _split_sentences(text: str) -> list[str]:
    compact = " ".join(text.split())
    if not compact:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s*", compact)
    return [part.strip() for part in parts if part.strip()]


def _pick_quote(query: str, full_text: str, snippet: str, max_sentences: int, max_chars: int) -> str:
    source_text = (full_text or "").strip() or (snippet or "").strip()
    if not source_text:
        return ""
    sentences = _split_sentences(source_text)
    if not sentences:
        base = source_text[:max_chars].rstrip()
        if len(source_text) > max_chars:
            base += "..."
        return f"...{base}..."

    query_tokens = _tokenize(query)
    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        lower_sentence = sentence.lower()
        overlap = sum(1 for token in set(query_tokens) if token in lower_sentence)
        weight = float(overlap * 2)
        if any(marker in sentence for marker in ["本质", "核心", "定义", "关键", "原因", "如何"]):
            weight += 0.8
        weight -= index * 0.03
        scored.append((weight, index, sentence))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_indices = sorted(item[1] for item in scored[:max_sentences])
    selected = [sentences[index] for index in top_indices]
    quote = "".join(selected).strip() or sentences[0].strip()
    if len(quote) > max_chars:
        quote = quote[:max_chars].rstrip() + "..."
    return f"...{quote}..."


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query PersonalKnowledgeAI and output compact JSON evidence.")
    parser.add_argument("--query", required=True, help="User query text.")
    parser.add_argument("--source", default=None, help="Optional source filter.")
    parser.add_argument("--series", default=None, help="Optional series filter.")
    parser.add_argument("--top-k", type=int, default=6, help="Retrieval top_k.")
    parser.add_argument("--alpha", type=float, default=0.45, help="Hybrid retrieval alpha.")
    parser.add_argument("--max-citations", type=int, default=2, help="Maximum citations in output.")
    parser.add_argument("--max-quote-sentences", type=int, default=2, help="Max sentences per quote.")
    parser.add_argument("--max-quote-chars", type=int, default=140, help="Max chars per quote.")
    return parser.parse_args()


def _citation_relevance(query: str, title: str, section: str, full_text: str, snippet: str, score: float) -> tuple[int, float]:
    tokens = _tokenize(query)
    if not tokens:
        return 0, float(score)
    text = f"{title} {section} {full_text or snippet}".lower()
    overlap = sum(1 for token in set(tokens) if token in text)
    return overlap, float(score)


def _compact_answer_hint(text: str, max_chars: int = 420) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def main() -> int:
    args = _parse_args()
    pkai_root = _resolve_pkai_root()
    pkai_src = pkai_root / "src"
    if not pkai_src.exists():
        print(json.dumps({"ok": False, "error": f"PersonalKnowledgeAI src not found at: {pkai_src}"}, ensure_ascii=False))
        return 1

    sys.path.insert(0, str(pkai_src))
    global PKAI_TOKENIZER

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from build_indexes import tokenize as pkai_tokenize  # type: ignore
            from rag_pipeline import ask  # type: ignore
        PKAI_TOKENIZER = pkai_tokenize
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"Failed to import rag pipeline: {exc}"}, ensure_ascii=False))
        return 1

    filters = {
        "source": args.source,
        "series": args.series,
    }

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            response = ask(
                query=args.query,
                filters=filters,
                top_k=args.top_k,
                alpha=args.alpha,
                prefer_llm=False,
            )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"RAG query failed: {exc}"}, ensure_ascii=False))
        return 1

    ranked_evidence = sorted(
        response.evidence,
        key=lambda item: _citation_relevance(
            query=args.query,
            title=item.doc_title,
            section=item.section_title,
            full_text=item.full_text,
            snippet=item.snippet,
            score=item.score,
        ),
        reverse=True,
    )
    query_tokens = _tokenize(args.query)
    if query_tokens:
        minimum_overlap = 1 if len(set(query_tokens)) <= 1 else 2
        ranked_evidence = [
            item
            for item in ranked_evidence
            if _citation_relevance(
                query=args.query,
                title=item.doc_title,
                section=item.section_title,
                full_text=item.full_text,
                snippet=item.snippet,
                score=item.score,
            )[0]
            >= minimum_overlap
        ]

    citations: list[dict] = []
    for item in ranked_evidence[: max(0, args.max_citations)]:
        quote = _pick_quote(
            query=args.query,
            full_text=item.full_text,
            snippet=item.snippet,
            max_sentences=max(1, args.max_quote_sentences),
            max_chars=max(60, args.max_quote_chars),
        )
        citations.append(
            {
                "id": item.ref_id,
                "title": item.doc_title,
                "section": item.section_title,
                "source": item.source,
                "series": item.series,
                "score": round(float(item.score), 4),
                "quote": quote,
                "snippet": item.snippet,
                "source_url": item.source_url,
                "chunk_id": item.chunk_id,
            }
        )

    payload = {
        "ok": True,
        "query": args.query,
        "standalone_query": response.standalone_query,
        "retrieval_mode": response.retrieval_mode,
        "confidence": response.confidence,
        "answer_hint": _compact_answer_hint(response.answer_markdown),
        "citation_count": len(citations),
        "citations": citations,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
