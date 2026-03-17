from __future__ import annotations

import argparse

from api_server import run as run_api_server
from mcp_server import run as run_mcp_server
from pipeline_ops import (
    command_build_all,
    command_chunk,
    command_classify,
    command_doctor,
    command_index,
    command_normalize,
    command_providers,
    command_review,
    ensure_dirs,
    read_chunks,
    read_documents,
    read_review_items,
    save_chunks,
    save_documents,
    save_review_queue,
    setup_logger,
    write_run_context,
    write_jsonl,
)


def command_serve(args, logger) -> int:
    run_api_server()
    return 0


def command_mcp_serve(args, logger) -> int:
    run_mcp_server()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PersonalKnowledgeAI local knowledge base pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize_parser = subparsers.add_parser("normalize", help="Normalize markdown files into documents.jsonl")
    normalize_parser.set_defaults(func=command_normalize)

    classify_parser = subparsers.add_parser("classify", help="Classify documents into taxonomy labels")
    classify_parser.add_argument("--mode", choices=["rule", "auto", "llm"], default="rule")
    classify_parser.set_defaults(func=command_classify)

    review_parser = subparsers.add_parser("review", help="CLI review for low-confidence documents")
    review_parser.add_argument("--limit", type=int, default=None)
    review_parser.add_argument("--doc-id", default=None)
    review_parser.set_defaults(func=command_review)

    chunk_parser = subparsers.add_parser("chunk", help="Generate chunks.jsonl")
    chunk_parser.set_defaults(func=command_chunk)

    index_parser = subparsers.add_parser("index", help="Build BM25 and vector indexes")
    index_parser.set_defaults(func=command_index)

    build_all_parser = subparsers.add_parser("build-all", help="Run normalize, classify, chunk, and index")
    build_all_parser.add_argument("--mode", choices=["rule", "auto", "llm"], default="rule")
    build_all_parser.set_defaults(func=command_build_all)

    ingest_parser = subparsers.add_parser("ingest", help="Run full ingestion for desktop sources and /knowledge markdown files")
    ingest_parser.add_argument("--mode", choices=["rule", "auto", "llm"], default="rule")
    ingest_parser.set_defaults(func=command_build_all)

    serve_parser = subparsers.add_parser("serve", help="Run FastAPI server")
    serve_parser.set_defaults(func=command_serve)

    mcp_parser = subparsers.add_parser("mcp-serve", help="Run MCP server")
    mcp_parser.set_defaults(func=command_mcp_serve)

    doctor_parser = subparsers.add_parser("doctor", help="Show runtime readiness and provider configuration")
    doctor_parser.set_defaults(func=command_doctor)

    providers_parser = subparsers.add_parser("providers", help="List configured embedding/generation/vector providers")
    providers_parser.set_defaults(func=command_providers)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logger = setup_logger()
    return args.func(args, logger)


if __name__ == "__main__":
    raise SystemExit(main())
