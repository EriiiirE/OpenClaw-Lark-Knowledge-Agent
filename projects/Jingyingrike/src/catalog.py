from __future__ import annotations

import logging
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlparse

from grouping import extract_topic, is_qa_title, normalize_section_topic
from models import CatalogEntry, CourseMeta
from utils import load_json, normalize_url, save_json, sha1_url


EXCLUDE_KEYWORDS = ["登录", "购买", "分享", "评论", "点赞", "更多", "下载APP"]
ARTICLE_LIST_API_PATH = "/api/pc/bauhinia/pc/class/purchase/article_list"
URL_RESOLVE_REOPEN_INTERVAL = 8


def _build_promo_markers(course_title: str) -> list[str]:
    markers = [course_title.strip()]
    if "·" in course_title:
        markers.append(course_title.split("·", 1)[1].strip())
    markers.extend(["下载得到", "得到APP", "扫码", "订阅", "课程宣传"])
    deduped: list[str] = []
    seen: set[str] = set()
    for marker in markers:
        clean = marker.strip()
        if clean and clean not in seen:
            seen.add(clean)
            deduped.append(clean)
    return deduped


def _normalize_catalog_title(title: str) -> str:
    return " ".join((title or "").split())


def _is_candidate_title(title: str) -> bool:
    if len(title.strip()) < 4:
        return False
    if any(keyword in title for keyword in EXCLUDE_KEYWORDS):
        return False
    return any(token in title for token in ("《", "问答", "答疑", "：", ":")) or any(char.isdigit() for char in title)


def _is_structured_catalog_title(title: str) -> bool:
    cleaned = title.strip()
    if len(cleaned) < 2:
        return False
    if any(keyword in cleaned for keyword in EXCLUDE_KEYWORDS):
        return False
    if "人学过" in cleaned or "已学" in cleaned:
        return False
    if "分" in cleaned and "秒" in cleaned and "|" in cleaned:
        return False
    return True


def _scroll_until_stable(page, logger: logging.Logger) -> None:
    last_count = -1
    stable_rounds = 0
    for _ in range(60):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1200)
        count = page.evaluate(
            """
            () => {
              const structured = document.querySelectorAll('li.single-content').length;
              if (structured) return structured;
              return Array.from(document.querySelectorAll('a[href], [data-href], [data-url]')).length;
            }
            """
        )
        logger.debug("Catalog scroll pass detected %s candidates", count)
        if count == last_count:
            stable_rounds += 1
            if stable_rounds >= 3:
                break
        else:
            stable_rounds = 0
            last_count = count


def _extract_course_title(page) -> str:
    return (
        page.evaluate(
            """
            () => {
              const h1 = document.querySelector('h1');
              if (h1 && h1.innerText.trim()) return h1.innerText.trim();
              const og = document.querySelector('meta[property="og:title"]');
              if (og && og.content) return og.content.trim();
              return document.title.trim();
            }
            """
        )
        or "Untitled Course"
    )


def _collect_catalog_candidates(page, base_url: str) -> list[dict[str, str]]:
    structured_candidates = page.evaluate(
        """
        () => {
          const readText = (node) => ((node && node.innerText) || '').trim();
          const findSectionTitle = (node) => {
            let current = node;
            while (current) {
              const parent = current.parentElement;
              if (!parent) break;
              const previous = parent.previousElementSibling;
              if (previous && previous.matches && previous.matches('.drawer-head')) {
                return readText(previous);
              }
              current = parent;
            }
            return '';
          };

          return Array.from(document.querySelectorAll('li.single-content'))
            .map((node, index) => {
              const text = (node.innerText || '').trim();
              const lines = text.split('\\n').map((line) => line.trim()).filter(Boolean);
              return {
                title: lines[0] || '',
                raw_text: text,
                section_topic: findSectionTitle(node),
                url: '',
                index
              };
            })
            .filter((item) => item.title);
        }
        """
    )
    if structured_candidates:
        return structured_candidates

    return page.evaluate(
        """
        ({ baseUrl }) => {
          const normalize = (raw) => {
            try {
              return new URL(raw, baseUrl).href;
            } catch (error) {
              return '';
            }
          };

          return Array.from(document.querySelectorAll('a[href], [data-href], [data-url]'))
            .map((node, index) => {
              const title = (
                node.innerText ||
                node.getAttribute('title') ||
                node.getAttribute('aria-label') ||
                ''
              ).trim();
              const rawUrl =
                node.getAttribute('href') ||
                node.getAttribute('data-href') ||
                node.getAttribute('data-url') ||
                '';
              return {
                title,
                url: normalize(rawUrl),
                index
              };
            })
            .filter((item) => item.title && item.url);
        }
        """,
        {"baseUrl": base_url},
    )


def _extract_article_index_from_payloads(payloads: list[dict], logger: logging.Logger) -> list[dict[str, str]]:
    logger.info("正在读取课程目录接口...")
    if not payloads:
        logger.warning("课程目录接口响应未捕获，将退回旧的目录解析方式。")
        return []
    article_list: list[dict] = []
    for payload in payloads:
        article_list.extend(payload.get("c", {}).get("article_list", []))
    records: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in article_list:
        title = _normalize_catalog_title(item.get("title", ""))
        enid = (item.get("enid") or "").strip()
        if not title or not enid:
            continue
        url = normalize_url(f"https://www.dedao.cn/course/article?id={enid}")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        records.append(
            {
                "title": title,
                "url": url,
            }
        )
    logger.info("课程目录接口返回 %s 条文章索引", len(records))
    return records


def _merge_api_urls(raw_candidates: list[dict[str, str]], api_records: list[dict[str, str]]) -> list[dict[str, str]]:
    if not api_records:
        return raw_candidates

    enriched = [dict(candidate) for candidate in raw_candidates]
    exact_matches: dict[str, deque[str]] = defaultdict(deque)
    for record in api_records:
        exact_matches[record["title"]].append(record["url"])

    for candidate in enriched:
        title = _normalize_catalog_title(candidate.get("title", ""))
        if candidate.get("url"):
            continue
        if exact_matches[title]:
            candidate["url"] = exact_matches[title].popleft()

    api_index = 0
    total_api = len(api_records)
    for candidate in enriched:
        if candidate.get("url"):
            continue
        title = _normalize_catalog_title(candidate.get("title", ""))
        while api_index < total_api:
            record = api_records[api_index]
            api_index += 1
            if record["title"] == title:
                candidate["url"] = record["url"]
                break
    return enriched


def ensure_catalog_entries_loaded(page, desired_count: int, logger: logging.Logger) -> None:
    for _ in range(80):
        count = page.evaluate("() => document.querySelectorAll('li.single-content').length")
        if count >= desired_count:
            return
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1200)
    logger.warning("Catalog only loaded %s entries while waiting for %s", count, desired_count)


def resolve_entry_urls(client, course_url: str, entries: list[CatalogEntry], logger: logging.Logger) -> list[CatalogEntry]:
    if not entries:
        return entries

    sorted_entries = sorted(entries, key=lambda item: item.order)
    page = None
    try:
        for index, entry in enumerate(sorted_entries, start=1):
            if page is None or (index - 1) % URL_RESOLVE_REOPEN_INTERVAL == 0:
                if page is not None:
                    page.close()
                logger.info("正在重新打开课程目录页以继续解析文章链接...")
                page = client.open_course_page(course_url)
                _scroll_until_stable(page, logger)

            logger.info("正在定位目录项 %s/%s：%s", index, len(sorted_entries), entry.title)
            target_index = entry.source_index or entry.order
            ensure_catalog_entries_loaded(page, target_index, logger)
            page.wait_for_timeout(500)
            clicked = page.evaluate(
                """
                (targetIndex) => {
                  const target = document.querySelectorAll('li.single-content')[targetIndex - 1];
                  if (!target) return false;
                  target.scrollIntoView({ block: 'center' });
                  target.click();
                  return true;
                }
                """,
                target_index,
            )
            if not clicked:
                raise RuntimeError(f"Catalog entry not found for source index {target_index}")
            page.wait_for_url("**/course/article?id=*", timeout=30000)
            page.wait_for_timeout(1500)
            entry.url = normalize_url(page.url)
            entry.id = sha1_url(entry.url)
            logger.debug(
                "Resolved article URL for order #%s (source #%s): %s -> %s",
                entry.order,
                target_index,
                entry.title,
                entry.url,
            )
            page.go_back(wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
        return entries
    finally:
        if page is not None:
            page.close()


def _cache_path_for(course_url: str, state_dir: Path) -> Path:
    return state_dir / "catalog_cache" / f"{sha1_url(course_url)}.json"


def _save_catalog_cache(cache_path: Path, course_meta: CourseMeta, entries: list[CatalogEntry]) -> None:
    save_json(
        cache_path,
        {
            "course_meta": course_meta.to_dict(),
            "entries": [entry.to_dict() for entry in entries],
        },
    )


def _load_catalog_cache(cache_path: Path) -> tuple[CourseMeta, list[CatalogEntry]]:
    payload = load_json(cache_path, default={})
    if not payload:
        raise FileNotFoundError(cache_path)
    course_meta = CourseMeta.from_dict(payload["course_meta"])
    entries = [CatalogEntry.from_dict(item) for item in payload["entries"]]
    return course_meta, entries


def load_catalog(client, course_url: str, state_dir: Path, logger: logging.Logger) -> tuple[CourseMeta, list[CatalogEntry]]:
    cache_path = _cache_path_for(course_url, state_dir)
    try:
        context = client._require_context()
        page = context.new_page()
        article_list_payloads: list[dict] = []

        def capture_article_list(resp) -> None:
            if ARTICLE_LIST_API_PATH not in resp.url:
                return
            try:
                article_list_payloads.append(resp.json())
            except Exception as exc:
                logger.debug("Failed to decode article list response: %s", exc)

        page.on("response", capture_article_list)
        try:
            logger.debug("Opening page: %s", course_url)
            page.goto(course_url, wait_until="domcontentloaded", timeout=45000)
            client._wait_for_ready_state(page)
            page.wait_for_timeout(1200)
            _scroll_until_stable(page, logger)
            page.wait_for_timeout(1500)
            course_title = _extract_course_title(page)
            raw_candidates = _collect_catalog_candidates(page, course_url)
            raw_candidates = _merge_api_urls(raw_candidates, _extract_article_index_from_payloads(article_list_payloads, logger))
        finally:
            page.close()
    except Exception:
        if cache_path.exists():
            logger.warning("Falling back to cached catalog: %s", cache_path)
            return _load_catalog_cache(cache_path)
        raise

    entries: list[CatalogEntry] = []
    seen_urls: set[str] = set()
    for candidate in raw_candidates:
        title = candidate["title"].strip()
        raw_url = candidate.get("url", "").strip()
        is_structured_candidate = "raw_text" in candidate or "section_topic" in candidate
        if is_structured_candidate:
            if not _is_structured_catalog_title(title):
                continue
        elif raw_url:
            if not _is_candidate_title(title):
                continue
        else:
            if not _is_structured_catalog_title(title):
                continue

        if raw_url:
            url = normalize_url(raw_url, course_url)
            parsed = urlparse(url)
            if "dedao.cn" not in parsed.netloc:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
        else:
            url = normalize_url(f"{course_url}#catalog-order-{len(entries) + 1}")

        entries.append(
            CatalogEntry(
                id=sha1_url(url),
                title=title,
                url=url,
                order=len(entries) + 1,
                source_index=int(candidate.get("index", len(entries))) + 1,
                section_topic=normalize_section_topic(candidate.get("section_topic", "")),
                raw_topic=extract_topic(title),
                assigned_topic=None,
                is_qa=is_qa_title(title),
            )
        )

    course_meta = CourseMeta(
        title=course_title,
        url=normalize_url(course_url),
        promo_markers=_build_promo_markers(course_title),
    )
    _save_catalog_cache(cache_path, course_meta, entries)
    logger.info("Catalog loaded with %s entries", len(entries))
    return course_meta, entries
