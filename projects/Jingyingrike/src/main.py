from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import traceback
from pathlib import Path

from catalog import load_catalog, resolve_entry_urls
from extractor import extract_article_text
from grouping import assign_topics, group_entries_by_topic, ordered_topic_names, select_topic_names
from models import ArticleRecord, ProgressRecord, STATUS_BLOCKED_RISK, STATUS_FAILED, STATUS_SUCCESS
from utils import PROJECT_ROOT, ensure_dir, load_json, now_iso, relative_to_root, resolve_project_path, save_json
from writer import write_topic_markdown


os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")


STATE_DIR = PROJECT_ROOT / "state"
OUTPUT_DIR = PROJECT_ROOT / "output_md"
LOG_DIR = PROJECT_ROOT / "logs"
SRC_DIR = PROJECT_ROOT / "src"
SUCCESS_RESTART_INTERVAL = 12


def ensure_project_layout() -> None:
    for path in [
        SRC_DIR,
        OUTPUT_DIR,
        STATE_DIR,
        LOG_DIR,
        STATE_DIR / "browser_profile",
        STATE_DIR / "article_cache",
        STATE_DIR / "catalog_cache",
    ]:
        ensure_dir(path)

    defaults = {
        STATE_DIR / "progress.json": {"course_url": None, "updated_at": None, "items": {}},
        STATE_DIR / "run_context.json": {},
        STATE_DIR / "unassigned.json": [],
    }
    for path, payload in defaults.items():
        if not path.exists():
            save_json(path, payload)


def create_logger() -> tuple[logging.Logger, Path]:
    ensure_dir(LOG_DIR)
    suffix = now_iso().replace(":", "").replace("-", "").replace("+", "_").replace("T", "_")
    log_path = LOG_DIR / f"run_{suffix}.log"

    logger = logging.getLogger("jingyingrike")
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
    payload = load_json(progress_path, default={"course_url": None, "updated_at": None, "items": {}})
    payload.setdefault("items", {})
    return payload


def save_progress(progress_path: Path, course_url: str, items: dict[str, ProgressRecord]) -> None:
    save_json(
        progress_path,
        {
            "course_url": course_url,
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


def write_unassigned(unassigned_entries: list) -> None:
    save_json(STATE_DIR / "unassigned.json", [entry.to_dict() for entry in unassigned_entries])


def resolve_out_dir(raw_out: str) -> Path:
    return ensure_dir(resolve_project_path(raw_out))


def rebuild_topics(out_dir: Path, selected_topics: list[str]) -> list[Path]:
    generated: list[Path] = []
    for topic in selected_topics:
        records: list[ArticleRecord] = []
        for cache_file in sorted((STATE_DIR / "article_cache").glob("*.json")):
            payload = load_json(cache_file, default=None)
            if not payload:
                continue
            record = ArticleRecord.from_dict(payload)
            if record.topic == topic:
                records.append(record)
        if records:
            generated.append(write_topic_markdown(topic, records, out_dir))
    return generated


def format_topic_lines(entries: list) -> list[str]:
    grouped_entries = group_entries_by_topic(entries)
    topic_names = ordered_topic_names(entries)
    lines: list[str] = []
    for index, topic in enumerate(topic_names, start=1):
        topic_entries = grouped_entries[topic]
        lines.append(
            f"{index:>3}. {topic} | {len(topic_entries)} lectures | orders {topic_entries[0].order}-{topic_entries[-1].order}"
        )
    return lines


def build_progress_record(*, entry, status: str, attempts: int, cache_path: Path | None, last_error: str | None) -> ProgressRecord:
    return ProgressRecord(
        id=entry.id,
        status=status,
        attempts=attempts,
        title=entry.title,
        url=entry.url,
        topic=entry.assigned_topic,
        cache_path=relative_to_root(cache_path) if cache_path else None,
        last_error=last_error,
        updated_at=now_iso(),
    )


def collect_course_entries(client, course_url: str, logger: logging.Logger) -> tuple[object, list]:
    logger.info("正在加载课程目录并识别专题...")
    client.ensure_logged_in(course_url)
    course_meta, catalog_entries = load_catalog(client, course_url, STATE_DIR, logger)
    assigned_entries, unassigned_entries = assign_topics(catalog_entries)
    write_unassigned(unassigned_entries)
    if unassigned_entries:
        logger.warning("Unassigned entries: %s", len(unassigned_entries))
    return course_meta, assigned_entries


def run_login(args: argparse.Namespace, logger: logging.Logger) -> int:
    from dedao_client import DedaoClient

    with DedaoClient(
        STATE_DIR / "browser_profile",
        logger,
        headless=False,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_retries=args.max_retries,
    ) as client:
        client.login(args.course_url)
    return 0


def run_topics(args: argparse.Namespace, logger: logging.Logger) -> int:
    from dedao_client import DedaoClient

    with DedaoClient(
        STATE_DIR / "browser_profile",
        logger,
        headless=args.headless,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_retries=args.max_retries,
    ) as client:
        _, assigned_entries = collect_course_entries(client, args.course_url, logger)

    topic_lines = format_topic_lines(assigned_entries)
    if not topic_lines:
        logger.info("No topics found.")
        return 0

    logger.info("Available topics: %s", len(topic_lines))
    for line in topic_lines:
        logger.info(line)
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

    from dedao_client import DedaoClient

    with DedaoClient(
        STATE_DIR / "browser_profile",
        logger,
        headless=args.headless,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_retries=args.max_retries,
    ) as client:
        course_meta, assigned_entries = collect_course_entries(client, args.course_url, logger)
        selected_topics = select_topic_names(
            assigned_entries,
            topic=args.topic,
            start_after_topic=args.start_after_topic,
            start_topic=args.start_topic,
            end_topic=args.end_topic,
            topic_limit=args.topic_limit,
        )
        if args.exclude_topic:
            excluded = set(args.exclude_topic)
            selected_topics = [topic for topic in selected_topics if topic not in excluded]
        if not selected_topics:
            logger.info("No catalog entries matched the current selection.")
            return 0

        all_selected_entries = [entry for entry in assigned_entries if entry.assigned_topic in selected_topics]
        batch_size = args.batch_size or len(selected_topics)
        topic_batches = [selected_topics[index : index + batch_size] for index in range(0, len(selected_topics), batch_size)]

        blocked = False
        for batch_index, topic_batch in enumerate(topic_batches, start=1):
            logger.info("Starting batch %s/%s: %s", batch_index, len(topic_batches), ", ".join(topic_batch))
            batch_entries = [entry for entry in all_selected_entries if entry.assigned_topic in topic_batch]
            unresolved_entries = [entry for entry in batch_entries if "/course/article?id=" not in entry.url]
            if unresolved_entries:
                logger.info("正在定位课程目录并解析本批次文章链接：%s 条", len(unresolved_entries))
                resolve_entry_urls(client, args.course_url, unresolved_entries, logger)
            grouped_entries = group_entries_by_topic(batch_entries)

            completed_topics = (batch_index - 1) * batch_size
            for topic_offset, topic in enumerate(topic_batch, start=1):
                topic_entries = sorted(grouped_entries[topic], key=lambda item: item.order)
                for lecture_index, entry in enumerate(topic_entries, start=1):
                    logger.info(
                        "[%s/%s topics][%s/%s lectures] %s | %s",
                        completed_topics + topic_offset,
                        len(selected_topics),
                        lecture_index,
                        len(topic_entries),
                        topic,
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
                            page = client.open_article_page(entry.url)
                            risk = client.detect_risk_or_captcha(page)
                            if risk:
                                if not args.headless and client.resolve_risk_interactively(page):
                                    risk = client.detect_risk_or_captcha(page)
                                if risk:
                                    progress_items[entry.id] = build_progress_record(
                                        entry=entry,
                                        status=STATUS_BLOCKED_RISK,
                                        attempts=base_attempts + attempt,
                                        cache_path=None,
                                        last_error=f"Detected risk or captcha prompt: {risk}",
                                    )
                                    save_progress(progress_path, args.course_url, progress_items)
                                    logger.error("Detected risk or captcha prompt: %s", risk)
                                    summary["blocked"] += 1
                                    blocked = True
                                    break

                            content = extract_article_text(page, course_meta)
                            record = ArticleRecord(
                                id=entry.id,
                                topic=entry.assigned_topic,
                                title=entry.title,
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
                            save_progress(progress_path, args.course_url, progress_items)
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
                                save_progress(progress_path, args.course_url, progress_items)
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
                    if success and summary["success"] % SUCCESS_RESTART_INTERVAL == 0:
                        client.restart_context(f"已连续完成 {summary['success']} 篇，主动释放内存")

                rebuild_topics(out_dir, [topic])
                if blocked:
                    break

            if blocked:
                break
            if batch_index < len(topic_batches) and args.batch_cooldown > 0:
                logger.info("Cooling down for %s seconds before next batch.", args.batch_cooldown)
                time.sleep(args.batch_cooldown)

    generated_files = rebuild_topics(out_dir, selected_topics)
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
    parser = argparse.ArgumentParser(description="Dedao personal learning archiver")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_shared_arguments(command_parser: argparse.ArgumentParser, *, crawl_only: bool = False) -> None:
        command_parser.add_argument("--course-url", required=True, help="得到课程主页 URL")
        command_parser.add_argument("--delay-min", type=float, default=2.0, help="最小抓取间隔秒数")
        command_parser.add_argument("--delay-max", type=float, default=4.0, help="最大抓取间隔秒数")
        command_parser.add_argument("--max-retries", type=int, default=2, help="单讲最大重试次数")
        command_parser.add_argument(
            "--headless",
            type=lambda value: str(value).lower() not in {"0", "false", "no"},
            default=True,
            help="抓取时是否使用无头浏览器，默认 true",
        )
        if crawl_only:
            command_parser.add_argument("--topic", help="只抓取指定专题")
            command_parser.add_argument("--start-after-topic", help="从指定专题之后开始连续抓取")
            command_parser.add_argument("--start-topic", help="从指定专题开始抓取")
            command_parser.add_argument("--end-topic", help="抓取到指定专题为止")
            command_parser.add_argument("--topic-limit", type=int, help="最多连续抓取的专题数量")
            command_parser.add_argument("--exclude-topic", action="append", default=[], help="排除指定专题，可重复传入")
            command_parser.add_argument("--batch-size", type=int, default=0, help="每批抓取的专题数量，0 表示不分批")
            command_parser.add_argument("--batch-cooldown", type=int, default=45, help="批次之间的冷却秒数")
            command_parser.add_argument("--out", default="output_md", help="Markdown 输出目录")
            command_parser.add_argument("--force", action="store_true", help="忽略成功缓存，强制重抓")

    login_parser = subparsers.add_parser("login", help="打开浏览器并人工登录")
    add_shared_arguments(login_parser)

    crawl_parser = subparsers.add_parser("crawl", help="抓取课程正文并输出 Markdown")
    add_shared_arguments(crawl_parser, crawl_only=True)

    topics_parser = subparsers.add_parser("topics", help="列出课程内可抓取的专题")
    add_shared_arguments(topics_parser)

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
        if getattr(args, "topic_limit", None) is not None and args.topic_limit <= 0:
            raise ValueError("--topic-limit must be greater than 0")
        if getattr(args, "batch_size", 0) < 0:
            raise ValueError("--batch-size must be 0 or greater")
        if getattr(args, "batch_cooldown", 0) < 0:
            raise ValueError("--batch-cooldown must be 0 or greater")

        if args.command == "login":
            return run_login(args, logger)
        if args.command == "crawl":
            return run_crawl(args, logger)
        if args.command == "topics":
            return run_topics(args, logger)
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
