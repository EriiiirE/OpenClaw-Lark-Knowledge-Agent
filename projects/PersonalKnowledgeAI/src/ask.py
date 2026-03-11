from __future__ import annotations

import argparse

from rag_pipeline import ask


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the PersonalKnowledgeAI RAG pipeline.")
    parser.add_argument("query", help="Question to ask the knowledge base.")
    parser.add_argument("--source", default=None, help="Optional source filter, e.g. jingyingrike or yexiu_wechat.")
    parser.add_argument("--series", default=None, help="Optional series filter.")
    parser.add_argument("--top-k", type=int, default=6, help="Number of final evidence blocks to consider.")
    parser.add_argument("--alpha", type=float, default=0.45, help="Hybrid retrieval alpha.")
    parser.add_argument("--retrieval-only", action="store_true", help="Disable LLM answer generation.")
    args = parser.parse_args()

    filters = {
        "source": args.source,
        "series": args.series,
    }
    response = ask(
        query=args.query,
        filters=filters,
        top_k=args.top_k,
        alpha=args.alpha,
        prefer_llm=not args.retrieval_only,
    )

    print(f"mode: {response.retrieval_mode}")
    print(f"confidence: {response.confidence}")
    print()
    print(response.answer_markdown)
    print()
    print("evidence:")
    for item in response.evidence:
        print(f"- {item.ref_id} {item.doc_title} / {item.section_title} | source={item.source} | score={item.score}")
        if item.source_url:
            print(f"  url: {item.source_url}")
        print(f"  snippet: {item.snippet}")


if __name__ == "__main__":
    main()
