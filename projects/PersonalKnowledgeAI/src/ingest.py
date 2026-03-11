from __future__ import annotations

import argparse

from main import command_build_all, ensure_dirs, setup_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest desktop sources and /knowledge markdown files into the PersonalKnowledgeAI index")
    parser.add_argument("--mode", choices=["rule", "auto", "llm"], default="rule")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ensure_dirs()
    logger = setup_logger()
    return command_build_all(args, logger)


if __name__ == "__main__":
    raise SystemExit(main())
