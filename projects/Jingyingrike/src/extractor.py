from __future__ import annotations

from html.parser import HTMLParser
from typing import Iterable

from models import CourseMeta


CONTENT_SELECTORS = [
    ".article-body",
    ".article-body-wrap",
    ".article-wrap",
    ".iget-articles",
    ".article",
    "main article",
    "main",
    '[role="main"]',
    ".left-content",
    ".article-main",
    ".course-article",
    ".article-content",
    ".content",
    ".rich-text",
    ".reader",
    ".detail",
]

REMOVAL_SELECTORS = [
    "img",
    "picture",
    "figure",
    "svg",
    "video",
    "audio",
    "canvas",
    "iframe",
    "button",
    "form",
    "nav",
    "footer",
    "aside",
    '[role="button"]',
    ".share",
    ".comment",
    ".recommend",
    ".related",
    ".ad",
    ".copyright",
    ".toolbar",
    ".like",
    ".reward",
    ".message-v2",
    ".message-list-wrap",
    ".iget-note-list",
    ".note-item-wrapper",
    ".note-wrap",
    ".player-control",
    ".course-nav",
    ".iget-prompt",
    ".prompt-main",
    ".add-topic-content",
]

DROP_LINE_PATTERNS = [
    "展开目录",
    "设置文本",
    "文字",
    "小字号 中字号 大字号",
    "支持快捷键 Ctrl +",
    "Alt + “+” 放大字号，",
    'Alt + "+" 放大字号，',
    "Ctrl + Alt",
    '+ “-” 缩小字号',
    '+ "-" 缩小字号',
]

STOP_LINE_MARKERS = [
    "划重点",
    "添加到笔记",
    "写笔记",
    "首次发布:",
    "我的留言",
    "用户留言",
    "写留言，与作者互动",
    "转发同时评论",
    "快速转发",
    "添加话题",
    "不参与话题",
    "最近使用",
    "全部话题",
    "确认离开此页面",
    "关闭悬浮窗",
    "打开悬浮窗",
    "很抱歉，没有找到相关内容",
]


class HtmlSnapshotExtractor(HTMLParser):
    def __init__(self, promo_markers: Iterable[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.ignored_depth = 0
        self.lines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        tag_lower = tag.lower()
        if tag_lower in {"script", "style", "button", "nav", "footer", "aside", "form", "svg", "video", "audio", "canvas", "iframe"}:
            self.ignored_depth += 1
            return
        if self.ignored_depth:
            return
        if tag_lower in {"img", "picture", "figure"}:
            marker_text = " ".join(
                filter(
                    None,
                    [
                        attrs_map.get("alt", ""),
                        attrs_map.get("title", ""),
                        attrs_map.get("aria-label", ""),
                    ],
                )
            ).strip()
            if marker_text:
                self.lines.append(marker_text)
            return
        if tag_lower in {"p", "div", "li", "blockquote", "pre", "h1", "h2", "h3", "h4", "br"}:
            self.lines.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in {"script", "style", "button", "nav", "footer", "aside", "form", "svg", "video", "audio", "canvas", "iframe"} and self.ignored_depth:
            self.ignored_depth -= 1
            return
        if self.ignored_depth:
            return
        if tag_lower in {"p", "div", "li", "blockquote", "pre", "h1", "h2", "h3", "h4"}:
            self.lines.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored_depth:
            return
        text = data.strip()
        if text:
            self.lines.append(text)


def normalize_extracted_text(text: str, promo_markers: Iterable[str]) -> str:
    lowered_markers = [marker.lower() for marker in promo_markers if marker]
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]

    blocks: list[str] = []
    start_collecting = False
    skipped_preamble = False
    for line in lines:
        if not line:
            continue
        lowered_line = line.lower()
        if line in DROP_LINE_PATTERNS:
            continue
        if line.startswith("转述："):
            start_collecting = True
            skipped_preamble = True
            continue
        if not start_collecting:
            if line.startswith("发刊词：") and len(line) <= 40:
                skipped_preamble = True
                continue
            if "分" in line and "秒" in line and len(line) <= 20:
                skipped_preamble = True
                continue
            if "精英日课" in line and "年度日更" in line:
                skipped_preamble = True
                continue
            if line.startswith("《") and len(line) <= 40:
                skipped_preamble = True
                continue
            if skipped_preamble or len(line) >= 24 or not blocks:
                start_collecting = True
            else:
                continue

        if start_collecting:
            promo_positions = [lowered_line.find(marker) for marker in lowered_markers if marker in lowered_line]
            if promo_positions:
                cutoff = min(position for position in promo_positions if position >= 0)
                line = line[:cutoff].strip()
                if line:
                    blocks.append(line)
                break

            stop_positions = [line.find(marker) for marker in STOP_LINE_MARKERS if marker in line]
            if stop_positions:
                cutoff = min(position for position in stop_positions if position >= 0)
                line = line[:cutoff].strip()
                if line and (not blocks or blocks[-1] != line):
                    blocks.append(line)
                break

        if blocks and blocks[-1] == line:
            continue
        blocks.append(line)

    return "\n\n".join(blocks).strip()


def extract_text_from_html_snapshot(html: str, promo_markers: Iterable[str]) -> str:
    parser = HtmlSnapshotExtractor(promo_markers)
    parser.feed(html)
    parser.close()
    return normalize_extracted_text("\n".join(parser.lines), promo_markers)


def extract_article_text(page, course_meta: CourseMeta) -> str:
    page.wait_for_function(
        """
        (selectors) => {
          const candidates = selectors
            .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
            .filter((element, index, array) => array.indexOf(element) === index)
            .filter((element) => !element.closest('footer, aside, nav'));
          return candidates.some((element) => ((element.innerText || '').trim()).length >= 200);
        }
        """,
        arg=CONTENT_SELECTORS,
        timeout=15000,
    )
    payload = page.evaluate(
        """
        ({ selectors, removalSelectors, promoMarkers }) => {
          const visibleTextLength = (element) => {
            const text = (element && element.innerText) ? element.innerText.trim() : "";
            return text.length;
          };
          const scoreCandidate = (element) => {
            if (!element) return -1;
            if (element.closest('footer, aside, nav')) return -1;
            const text = (element.innerText || '').trim();
            if (!text) return -1;
            let score = text.length;
            if (element.tagName === 'MAIN') score += 1000;
            if (element.tagName === 'ARTICLE') score += 300;
            const className = typeof element.className === 'string' ? element.className : '';
            if (/footer|recommend|related|comment|copyright/i.test(className)) score -= 5000;
            if (/iget-pc|scroll-wrapper|add-topic|prompt|message|note-list/i.test(className)) score -= 7000;
            if (/content|article|reader|detail|main/i.test(className)) score += 400;
            if (/article-body|rich-text-panel/i.test(className)) score += 8000;
            if (/article-body-wrap|article-wrap|iget-articles/i.test(className)) score += 2000;
            return score;
          };

          const candidates = selectors
            .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
            .filter((element, index, array) => array.indexOf(element) === index)
            .filter((element) => !element.closest('footer, aside'));
          let root = candidates.sort((a, b) => scoreCandidate(b) - scoreCandidate(a))[0] || null;
          if (!root) {
            root = Array.from(document.querySelectorAll('article, main, section, div'))
              .filter((element) => !element.closest('footer, aside, nav'))
              .sort((a, b) => scoreCandidate(b) - scoreCandidate(a))[0] || null;
          }

          if (!root) {
            return { text: "", containerFound: false };
          }

          const clone = root.cloneNode(true);
          const markers = promoMarkers.filter(Boolean).map((marker) => marker.toLowerCase());

          clone.querySelectorAll(removalSelectors.join(",")).forEach((node) => {
            const textBits = [
              node.getAttribute && node.getAttribute("alt"),
              node.getAttribute && node.getAttribute("title"),
              node.getAttribute && node.getAttribute("aria-label"),
              node.textContent
            ].filter(Boolean);
            const markerText = textBits.join(" ").trim();
            if (markerText && markers.some((marker) => markerText.toLowerCase().includes(marker))) {
              const placeholder = document.createElement("div");
              placeholder.textContent = markerText;
              node.replaceWith(placeholder);
              return;
            }
            node.remove();
          });

          const text = clone.innerText ? clone.innerText.trim() : "";
          return { text, containerFound: true };
        }
        """,
        {
            "selectors": CONTENT_SELECTORS,
            "removalSelectors": REMOVAL_SELECTORS,
            "promoMarkers": course_meta.promo_markers,
        },
    )
    text = normalize_extracted_text(payload.get("text", ""), course_meta.promo_markers)
    if payload.get("containerFound") and len(text) < 80:
        raise ValueError("Extracted text is too short; selector likely failed")
    return text
