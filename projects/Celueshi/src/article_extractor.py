from __future__ import annotations

from collections.abc import Iterable

from playwright.sync_api import Page

from utils import normalize_text


ARTICLE_TRUNCATE_MARKERS = [
    "报名链接",
    "试听课链接",
    "购课相关咨询请添加",
    "助理微信",
    "写留言",
    "精选留言",
    "评论区",
    "赞赏作者",
    "阅读原文",
    "上一篇",
    "下一篇",
]
ARTICLE_DROP_EXACT_LINES = {
    "学习策略师",
    "策略师——叶修",
    "原创",
}
ARTICLE_DROP_CONTAINS = [
    "微信扫一扫",
    "长按识别二维码",
    "喜欢作者",
    "赞赏",
]


def clean_article_blocks(blocks: Iterable[str], title: str) -> str:
    cleaned: list[str] = []
    normalized_title = normalize_text(title)
    for raw_block in blocks:
        text = normalize_text(raw_block)
        if not text:
            continue
        if text == normalized_title:
            continue
        if text in ARTICLE_DROP_EXACT_LINES:
            continue
        if any(marker in text for marker in ARTICLE_DROP_CONTAINS):
            continue
        if any(marker in text for marker in ARTICLE_TRUNCATE_MARKERS):
            break
        if cleaned and text == cleaned[-1]:
            continue
        cleaned.append(text)
    return "\n\n".join(cleaned).strip()


def extract_article_text(page: Page, fallback_title: str | None = None) -> tuple[str, str]:
    page.wait_for_selector("#js_content, .rich_media_content", timeout=15000)
    payload = page.evaluate(
        """
        () => {
          const titleNode =
            document.querySelector('#activity-name') ||
            document.querySelector('.rich_media_title') ||
            document.querySelector('h1');
          const root =
            document.querySelector('#js_content') ||
            document.querySelector('.rich_media_content');
          if (!root) {
            return { title: titleNode ? titleNode.innerText.trim() : '', blocks: [] };
          }
          const clone = root.cloneNode(true);
          const removeSelectors = [
            'img',
            'svg',
            'video',
            'audio',
            'iframe',
            'canvas',
            'picture',
            'figure',
            'style',
            'script',
            '.js_audio_frame',
            '.js_weapp_display_element',
            '.weui-media-box',
            '.qr_code_pc_outer',
            '.rich_media_tool',
            '.reward_area',
            '.original_primary_card_tips',
            '.original_area_primary',
            '.biz_link_card_box',
            '.js_product_container',
            '.js_insertlocalvideo',
            '.js_ad_link',
            '.qr_code_pc',
          ];
          clone.querySelectorAll(removeSelectors.join(',')).forEach((node) => node.remove());

          let blocks = Array.from(clone.querySelectorAll('p, li, blockquote, pre, h1, h2, h3, h4'))
            .map((node) => (node.innerText || '').trim())
            .filter(Boolean);
          if (blocks.length < 3) {
            blocks = (clone.innerText || '')
              .split(/\\n+/)
              .map((line) => line.trim())
              .filter(Boolean);
          }
          return {
            title: titleNode ? titleNode.innerText.trim() : '',
            blocks,
          };
        }
        """
    )
    title = normalize_text(payload.get("title") or fallback_title or "")
    content = clean_article_blocks(payload.get("blocks") or [], title)
    if len(content) < 40:
        raise ValueError("Extracted article content is too short")
    return title or normalize_text(fallback_title or "Untitled"), content
