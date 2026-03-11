from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from models import DirectoryEntry, DirectoryMeta
from utils import load_json, normalize_text, normalize_wechat_url, save_json, sha1_url


DIRECTORY_STOP_MARKERS = [
    "报名链接",
    "试听课链接",
    "写留言",
]
DIRECTORY_IGNORE_HEADINGS = {
    "寻宝地图",
}


def _directory_cache_path(state_dir: Path, index_url: str) -> Path:
    return state_dir / "directory_cache" / f"{sha1_url(index_url)}.json"


def extract_directory_items(page: Page) -> tuple[DirectoryMeta, list[dict]]:
    payload = page.evaluate(
        f"""
        () => {{
          const titleNode =
            document.querySelector('#activity-name') ||
            document.querySelector('.rich_media_title') ||
            document.querySelector('h1');
          const root =
            document.querySelector('#js_content section') ||
            document.querySelector('#js_content') ||
            document.querySelector('.rich_media_content');
          const stopMarkers = {DIRECTORY_STOP_MARKERS!r};
          if (!root) {{
            return {{
              title: titleNode ? titleNode.innerText.trim() : document.title,
              items: [],
            }};
          }}

          const maxFontPx = (element) => {{
            let maxValue = parseFloat(window.getComputedStyle(element).fontSize) || 0;
            element.querySelectorAll('*').forEach((child) => {{
              maxValue = Math.max(maxValue, parseFloat(window.getComputedStyle(child).fontSize) || 0);
            }});
            return maxValue;
          }};

          const normalize = (value) => (value || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();
          const items = [];
          let order = 0;
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);

          while (walker.nextNode()) {{
            const node = walker.currentNode;
            if (!(node instanceof HTMLElement)) continue;
            const tag = node.tagName;

            if (tag === 'A') {{
              const href = node.getAttribute('href') || '';
              const text = normalize(node.innerText);
              if (href.includes('mp.weixin.qq.com/s') && text) {{
                items.push({{ kind: 'link', text, href, fontPx: maxFontPx(node), order: order++ }});
              }}
              continue;
            }}

            if (tag !== 'P' && tag !== 'DIV') continue;
            if (node.querySelector('a[href*="mp.weixin.qq.com/s"]')) continue;
            const text = normalize(node.innerText);
            if (!text) continue;
            if (stopMarkers.some((marker) => text.includes(marker))) break;
            const fontPx = maxFontPx(node);
            if (fontPx < 16 || text.length > 30) continue;
            items.push({{ kind: 'heading', text, href: null, fontPx, order: order++ }});
          }}

          return {{
            title: titleNode ? titleNode.innerText.trim() : document.title,
            items,
          }};
        }}
        """
    )
    meta = DirectoryMeta(title=normalize_text(payload.get("title") or "微信公众号目录"), url=page.url)
    return meta, payload.get("items") or []


def assign_directory_entries(index_url: str, raw_items: list[dict]) -> list[DirectoryEntry]:
    entries: list[DirectoryEntry] = []
    current_category: str | None = None
    current_section: str | None = None
    seen: set[tuple[str, str, str]] = set()

    for item in raw_items:
        kind = item.get("kind")
        text = normalize_text(item.get("text", ""))
        if not text:
            continue

        if kind == "heading":
            if text in DIRECTORY_IGNORE_HEADINGS:
                continue
            font_px = float(item.get("fontPx") or 0)
            if font_px >= 19:
                current_category = text
                current_section = None
            elif font_px >= 16.5 and current_category:
                current_section = text
            continue

        if kind != "link" or not current_category:
            continue

        section = current_section or current_category
        url = normalize_wechat_url(item.get("href", ""), base_url=index_url)
        dedupe_key = (current_category, section, url)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        entries.append(
            DirectoryEntry(
                id=sha1_url(url),
                title=text,
                url=url,
                order=len(entries) + 1,
                category=current_category,
                section=section,
            )
        )
    return entries


def load_directory(client, index_url: str, state_dir: Path, logger) -> tuple[DirectoryMeta, list[DirectoryEntry]]:
    cache_path = _directory_cache_path(state_dir, index_url)
    page = client.open_page(index_url, expected="directory")
    try:
        risk = client.detect_block(page)
        if risk and client.resolve_block_interactively(page, index_url):
            risk = client.detect_block(page)
        if risk:
            raise RuntimeError(f"Directory page blocked by WeChat: {risk}")
        meta, raw_items = extract_directory_items(page)
        entries = assign_directory_entries(index_url, raw_items)
        payload = {
            "meta": meta.to_dict(),
            "items": [entry.to_dict() for entry in entries],
        }
        save_json(cache_path, payload)
        logger.info("目录解析完成：%s entries", len(entries))
        return meta, entries
    except Exception:
        cached = load_json(cache_path, default=None)
        if cached:
            logger.warning("目录页解析失败，回退到缓存。")
            meta = DirectoryMeta.from_dict(cached["meta"])
            entries = [DirectoryEntry.from_dict(item) for item in cached["items"]]
            return meta, entries
        raise
    finally:
        page.close()
