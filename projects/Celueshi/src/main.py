from __future__ import annotations

import argparse
import logging
import sys
import time
import traceback
from pathlib import Path

from article_extractor import extract_article_text
from directory_parser import load_directory
from grouping import group_entries, ordered_catalog_lines, select_entries
from models import ArticleRecord, ProgressRecord, STATUS_BLOCKED_RISK, STATUS_FAILED, STATUS_SKIPPED, STATUS_SUCCESS
from utils import PROJECT_ROOT, ensure_dir, load_json, now_iso, relative_to_root, resolve_project_path, save_json
from wechat_client import WechatClient
from writer import write_markdown

STATE_DIR = PROJECT_ROOT / "state"
OUTPUT_DIR = PROJECT_ROOT / "output_md"
LOG_DIR = PROJECT_ROOT / "logs"
SRC_DIR = PROJECT_ROOT / "src"
SUCCESS_RESTART_INTERVAL = 20


def ensure_project_layout() -> None:
    for path in [
        SRC_DIR,
        OUTPUT_DIR,
        STATE_DIR,
        LOG_DIR,
        STATE_DIR / "browser_profile",
        STATE_DIR / "article_cache",
        STATE_DIR / "directory_cache",
    ]:
        ensure_dir(path)
    defaults = {
        STATE_DIR / "progress.json": {"index_url": None, "updated_at": None, "items": {}},
        STATE_DIR / "run_context.json": {},
    }
    for path, payload in defaults.items():
        if not path.exists():
            save_json(path, payload)


def create_logger() -> tuple[logging.Logger, Path]:
    ensure_dir(LOG_DIR)
    suffix = now_iso().replace(":", "").replace("-", "").replace("+", "_").replace("T", "_")
    log_path = LOG_DIR / f"run_{suffix}.log"
    logger = logging.getLogger("celueshi")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)
    return logger, log_path


def load_progress(progress_path: Path) -> dict:
    payload = load_json(progress_path, default={"index_url": None, "updated_at": None, "items": {}})
    payload.setdefault("items", {})
    return payload


def save_progress(progress_path: Path, index_url: str, items: dict[str, ProgressRecord]) -> None:
    save_json(
        progress_path,
        {
            "index_url": index_url,
            "updated_at": now_iso(),
            "items": {item_id: record.to_dict() for item_id, record in items.items()},
        },
    )


def update_run_context(command: str, args: argparse.Namespace, log_path: Path) -> None:
    save_json(
        STATE_DIR / "run_context.json",
        {
            "command": command,
            "argv": vars(args),
            "log_path": relative_to_root(log_path),
            "updated_at": now_iso(),
        },
    )


def article_cache_path(article_id: str) -> Path:
    return STATE_DIR / "article_cache" / f"{article_id}.json"


def save_article_record(record: ArticleRecord) -> Path:
    cache_path = article_cache_path(record.id)
    save_json(cache_path, record.to_dict())
    return cache_path


def resolve_out_dir(raw_out: str) -> Path:
    return ensure_dir(resolve_project_path(raw_out))


def rebuild_outputs(out_dir: Path, selected_entries: list) -> list[Path]:
    grouped = group_entries(selected_entries)
    generated: list[Path] = []
    for category, section in grouped:
        records: list[ArticleRecord] = []
        for cache_file in sorted((STATE_DIR / "article_cache").glob("*.json")):
            payload = load_json(cache_file, default=None)
            if not payload:
                continue
            record = ArticleRecord.from_dict(payload)
            if record.category == category and record.section == section:
                records.append(record)
        if records:
            generated.append(write_markdown(category, section, records, out_dir))
    return generated


def build_progress_record(*, entry, status: str, attempts: int, cache_path: Path | None, last_error: str | None) -> ProgressRecord:
    return ProgressRecord(
        id=entry.id,
        status=status,
        attempts=attempts,
        title=entry.title,
        url=entry.url,
        category=entry.category,
        section=entry.section,
        cache_path=relative_to_root(cache_path) if cache_path else None,
        last_error=last_error,
        updated_at=now_iso(),
    )


def print_catalog(entries: list, logger: logging.Logger) -> None:
    lines = ordered_catalog_lines(entries)
    if not lines:
        logger.info("No catalog groups found.")
        return
    logger.info("Catalog groups: %s", len(lines))
    for line in lines:
        logger.info(line)


def run_catalog(args: argparse.Namespace, logger: logging.Logger) -> int:
    with WechatClient(
        STATE_DIR / "browser_profile",
        logger,
        headless=args.headless,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_retries=args.max_retries,
    ) as client:
        logger.info("正在加载微信公众号目录页...")
        _, entries = load_directory(client, args.index_url, STATE_DIR, logger)
    print_catalog(entries, logger)
    return 0


def run_crawl(args: argparse.Namespace, logger: logging.Logger) -> int:
    out_dir = resolve_out_dir(args.out)
    progress_path = STATE_DIR / "progress.json"
    progress_payload = load_progress(progress_path)
    progress_items = {
        item_id: ProgressRecord.from_dict(record)
        for item_id, record in progress_payload.get("items", {}).items()
    }
    summary = {"success": 0, "skipped": 0, "failed": 0, "blocked": 0}

    with WechatClient(
        STATE_DIR / "browser_profile",
        logger,
        headless=args.headless,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_retries=args.max_retries,
    ) as client:
        logger.info("正在加载微信公众号目录页...")
        _, entries = load_directory(client, args.index_url, STATE_DIR, logger)
        entries = select_entries(entries, category=args.category, section=args.section)
        if not entries:
            logger.info("No entries matched the current selection.")
            return 0

        grouped = group_entries(entries)
        logger.info("准备抓取 %s 个文档分组，%s 篇文章。", len(grouped), len(entries))

        blocked = False
        for group_index, ((category, section), group_entries_list) in enumerate(grouped.items(), start=1):
            label = category if category == section else f"{category} / {section}"
            logger.info("开始分组 %s/%s：%s", group_index, len(grouped), label)

            for article_index, entry in enumerate(group_entries_list, start=1):
                logger.info(
                    "[%s/%s groups][%s/%s articles] %s | %s",
                    group_index,
                    len(grouped),
                    article_index,
                    len(group_entries_list),
                    label,
                    entry.title,
                )
                cache_path = article_cache_path(entry.id)
                previous = progress_items.get(entry.id)
                if not args.force and previous and previous.status == STATUS_SUCCESS and cache_path.exists():
                    summary["skipped"] += 1
                    continue

                last_error: str | None = None
                success = False
                base_attempts = previous.attempts if previous else 0
                for attempt in range(1, args.max_retries + 2):
                    page = None
                    try:
                        page = client.open_page(entry.url, expected="article")
                        risk = client.detect_block(page)
                        resolved_manually = False
                        if risk and client.resolve_block_interactively(page, entry.url):
                            risk = client.detect_block(page)
                            resolved_manually = risk is None
                        if risk:
                            progress_items[entry.id] = build_progress_record(
                                entry=entry,
                                status=STATUS_BLOCKED_RISK,
                                attempts=base_attempts + attempt,
                                cache_path=None,
                                last_error=f"Detected block page: {risk}",
                            )
                            save_progress(progress_path, args.index_url, progress_items)
                            logger.error("检测到微信校验/风控页：%s", risk)
                            summary["blocked"] += 1
                            blocked = True
                            break
                        deleted_reason = client.detect_deleted(page)
                        if deleted_reason:
                            progress_items[entry.id] = build_progress_record(
                                entry=entry,
                                status=STATUS_SKIPPED,
                                attempts=base_attempts + attempt,
                                cache_path=None,
                                last_error=deleted_reason,
                            )
                            save_progress(progress_path, args.index_url, progress_items)
                            logger.warning("文章已删除，自动跳过：%s", entry.title)
                            summary["skipped"] += 1
                            break
                        if resolved_manually and args.post_verify_cooldown > 0:
                            logger.info("人工验证已通过，冷却 %s 秒后继续。", args.post_verify_cooldown)
                            time.sleep(args.post_verify_cooldown)

                        actual_title, content = extract_article_text(page, fallback_title=entry.title)
                        record = ArticleRecord(
                            id=entry.id,
                            category=entry.category,
                            section=entry.section,
                            title=actual_title or entry.title,
                            url=entry.url,
                            order=entry.order,
                            content=content,
                            fetched_at=now_iso(),
                        )
                        cache_path = save_article_record(record)
                        progress_items[entry.id] = build_progress_record(
                            entry=entry,
                            status=STATUS_SUCCESS,
                            attempts=base_attempts + attempt,
                            cache_path=cache_path,
                            last_error=None,
                        )
                        save_progress(progress_path, args.index_url, progress_items)
                        summary["success"] += 1
                        success = True
                        break
                    except Exception as exc:
                        last_error = f"{exc.__class__.__name__}: {exc}"
                        logger.error("Failed to crawl %s", entry.url)
                        logger.debug("%s", traceback.format_exc())
                        if attempt > args.max_retries:
                            progress_items[entry.id] = build_progress_record(
                                entry=entry,
                                status=STATUS_FAILED,
                                attempts=base_attempts + attempt,
                                cache_path=None,
                                last_error=last_error,
                            )
                            save_progress(progress_path, args.index_url, progress_items)
                            summary["failed"] += 1
                    finally:
                        if page is not None:
                            page.close()

                    if blocked:
                        break

                if blocked:
                    break
                if success or last_error:
                    client.polite_pause()
                if success and args.pause_every > 0 and article_index % args.pause_every == 0:
                    logger.info("已完成 %s 篇，额外冷却 %s 秒。", article_index, args.pause_seconds)
                    time.sleep(args.pause_seconds)
                if success and summary["success"] and summary["success"] % SUCCESS_RESTART_INTERVAL == 0:
                    client.restart_context(f"已完成 {summary['success']} 篇，主动释放内存")

            rebuild_outputs(out_dir, group_entries_list)
            if blocked:
                break
            if group_index < len(grouped) and args.batch_cooldown > 0:
                logger.info("Cooling down for %s seconds before next group.", args.batch_cooldown)
                time.sleep(args.batch_cooldown)

    generated_files = rebuild_outputs(out_dir, entries)
    logger.info(
        "Summary: success=%s skipped=%s failed=%s blocked=%s generated=%s",
        summary["success"],
        summary["skipped"],
        summary["failed"],
        summary["blocked"],
        len(generated_files),
    )
    return 1 if blocked else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WeChat personal article archiver")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_shared_arguments(command_parser: argparse.ArgumentParser, *, crawl_only: bool = False) -> None:
        command_parser.add_argument("--index-url", required=True, help="微信公众号目录页 URL")
        command_parser.add_argument("--delay-min", type=float, default=2.0, help="最小抓取间隔秒数")
        command_parser.add_argument("--delay-max", type=float, default=4.0, help="最大抓取间隔秒数")
        command_parser.add_argument("--max-retries", type=int, default=2, help="单篇最大重试次数")
        command_parser.add_argument(
            "--headless",
            type=lambda value: str(value).lower() not in {"0", "false", "no"},
            default=False,
            help="是否使用无头浏览器，默认 false",
        )
        if crawl_only:
            command_parser.add_argument("--category", help="只抓取指定一级分类")
            command_parser.add_argument("--section", help="只抓取指定二级分类")
            command_parser.add_argument("--batch-cooldown", type=int, default=60, help="分组之间冷却秒数")
            command_parser.add_argument("--pause-every", type=int, default=5, help="每抓多少篇额外暂停一次，0 表示关闭")
            command_parser.add_argument("--pause-seconds", type=int, default=45, help="额外暂停秒数")
            command_parser.add_argument("--post-verify-cooldown", type=int, default=60, help="人工验证通过后的冷却秒数")
            command_parser.add_argument("--out", default="output_md", help="Markdown 输出目录")
            command_parser.add_argument("--force", action="store_true", help="忽略成功缓存，强制重抓")

    crawl_parser = subparsers.add_parser("crawl", help="抓取目录页里的公众号文章并输出 Markdown")
    add_shared_arguments(crawl_parser, crawl_only=True)

    catalog_parser = subparsers.add_parser("catalog", help="列出目录页里的分类和分组")
    add_shared_arguments(catalog_parser)

    return parser


def main() -> int:
    ensure_project_layout()
    parser = build_parser()
    args = parser.parse_args()
    logger, log_path = create_logger()
    update_run_context(args.command, args, log_path)
    logger.info("Project root: %s", PROJECT_ROOT)

    try:
        if args.delay_min < 0 or args.delay_max < 0 or args.delay_max < args.delay_min:
            raise ValueError("Invalid delay range")
        if getattr(args, "batch_cooldown", 0) < 0:
            raise ValueError("--batch-cooldown must be 0 or greater")
        if getattr(args, "pause_every", 0) < 0:
            raise ValueError("--pause-every must be 0 or greater")
        if getattr(args, "pause_seconds", 0) < 0:
            raise ValueError("--pause-seconds must be 0 or greater")
        if getattr(args, "post_verify_cooldown", 0) < 0:
            raise ValueError("--post-verify-cooldown must be 0 or greater")
        if args.command == "catalog":
            return run_catalog(args, logger)
        if args.command == "crawl":
            return run_crawl(args, logger)
        raise ValueError(f"Unsupported command: {args.command}")
    except ValueError as exc:
        logger.error(str(exc))
        return 2
    except Exception as exc:
        logger.error("%s: %s", exc.__class__.__name__, exc)
        logger.debug("%s", traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
