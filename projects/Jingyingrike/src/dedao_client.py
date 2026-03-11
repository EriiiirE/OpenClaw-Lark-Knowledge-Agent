from __future__ import annotations

import logging
import random
import time
from pathlib import Path

from playwright.sync_api import (
    BrowserContext,
    Page,
    Playwright,
    Request,
    Route,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from utils import ensure_dir


RISK_KEYWORDS = [
    "验证码",
    "滑动验证",
    "访问异常",
    "风险提示",
    "请稍后再试",
    "操作过于频繁",
]
LOGIN_GATE_KEYWORDS = [
    "登录后查看",
    "扫码登录",
    "立即登录",
]
READY_SELECTORS = [
    ".article-body",
    ".article-body-wrap",
    ".article-wrap",
    ".iget-articles",
    ".article",
    "main",
    "article",
    '[role="main"]',
    ".course-detail",
    ".catalog",
    ".album",
]
BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}


class DedaoClient:
    def __init__(
        self,
        profile_dir: Path,
        logger: logging.Logger,
        *,
        headless: bool,
        delay_min: float = 2.0,
        delay_max: float = 4.0,
        max_retries: int = 2,
    ) -> None:
        self.profile_dir = ensure_dir(profile_dir)
        self.logger = logger
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None

    def __enter__(self) -> "DedaoClient":
        self.playwright = sync_playwright().start()
        self._launch_context()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._close_context()
        if self.playwright is not None:
            self.playwright.stop()
            self.playwright = None

    def _launch_context(self) -> None:
        if self.playwright is None:
            raise RuntimeError("Playwright is not initialized")
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            viewport={"width": 1440, "height": 960},
        )
        self.context.set_default_navigation_timeout(45000)
        self.context.set_default_timeout(45000)
        self.context.route("**/*", self._route_request)
        for page in list(self.context.pages):
            if page.url == "about:blank":
                page.close()

    def _close_context(self) -> None:
        if self.context is not None:
            try:
                self.context.close()
            except Exception as exc:
                self.logger.debug("Ignoring browser context close error: %s", exc)
            finally:
                self.context = None

    def restart_context(self, reason: str) -> None:
        self.logger.info("正在重启浏览器上下文：%s", reason)
        self._close_context()
        self._launch_context()

    def _route_request(self, route: Route, request: Request) -> None:
        resource_type = request.resource_type
        url = request.url.lower()
        if resource_type in BLOCKED_RESOURCE_TYPES:
            route.abort()
            return
        if any(url.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".mp4", ".mp3", ".woff", ".woff2", ".ttf", ".otf")):
            route.abort()
            return
        route.continue_()

    def _require_context(self) -> BrowserContext:
        if self.context is None:
            raise RuntimeError("Browser context is not initialized")
        return self.context

    def _wait_for_ready_state(self, page: Page) -> None:
        for selector in READY_SELECTORS:
            try:
                page.wait_for_selector(selector, timeout=5000)
                return
            except PlaywrightTimeoutError:
                continue
        page.wait_for_timeout(1500)

    def detect_risk_or_captcha(self, page: Page) -> str | None:
        try:
            result = page.evaluate(
                """
                (riskKeywords) => {
                  const isVisible = (node) => {
                    if (!node) return false;
                    const style = window.getComputedStyle(node);
                    const rect = node.getBoundingClientRect();
                    return style.display !== 'none' &&
                      style.visibility !== 'hidden' &&
                      rect.width > 0 &&
                      rect.height > 0;
                  };

                  const visibleTexts = Array.from(document.querySelectorAll('body *'))
                    .filter((node) => isVisible(node))
                    .map((node) => (node.innerText || '').trim())
                    .filter(Boolean);

                  const contentSelectors = [
                    '.article-body-wrap',
                    '.article-wrap',
                    '.iget-articles',
                    '.article',
                    'main',
                    '[role="main"]'
                  ];
                  const contentCandidates = contentSelectors
                    .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
                    .filter((node, index, array) => array.indexOf(node) === index)
                    .filter((node) => !node.closest('footer, aside, nav'))
                    .map((node) => (node.innerText || '').trim());

                  const contentText = contentCandidates.sort((a, b) => b.length - a.length)[0] || '';
                  const contentLooksReadable =
                    contentText.length >= 500 &&
                    !contentText.includes('登录后查看') &&
                    !contentText.includes('扫码登录');

                  for (const keyword of riskKeywords) {
                    const matched = visibleTexts.find((text) => text.includes(keyword));
                    if (matched && !contentLooksReadable) {
                      return {
                        keyword,
                        matchedText: matched.slice(0, 200),
                        contentLooksReadable
                      };
                    }
                  }

                  return {
                    keyword: null,
                    matchedText: '',
                    contentLooksReadable
                  };
                }
                """,
                RISK_KEYWORDS,
            )
        except PlaywrightTimeoutError:
            return None

        keyword = result.get("keyword")
        if keyword:
            self.logger.debug("Risk detector matched %s with visible text: %s", keyword, result.get("matchedText", ""))
        return keyword

    def _page_has_catalog_candidates(self, page: Page) -> bool:
        return bool(
            page.evaluate(
                """
                () => Array.from(document.querySelectorAll('a[href], [data-href], [data-url], li.single-content'))
                  .map((node) => (node.innerText || node.getAttribute?.('title') || '').trim())
                  .filter((text) => text.length >= 4)
                  .length
                """
            )
        )

    def page_requires_login(self, page: Page) -> bool:
        body_text = page.locator("body").inner_text(timeout=3000)
        return any(keyword in body_text for keyword in LOGIN_GATE_KEYWORDS)

    def open_page(self, url: str) -> Page:
        context = self._require_context()
        page = context.new_page()
        self.logger.debug("Opening page: %s", url)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self._wait_for_ready_state(page)
            page.wait_for_timeout(1200)
            return page
        except Exception:
            page.close()
            raise

    def fetch_page(self, url: str) -> Page:
        return self.open_page(url)

    def open_course_page(self, course_url: str) -> Page:
        return self.open_page(course_url)

    def open_article_page(self, article_url: str) -> Page:
        return self.open_page(article_url)

    def ensure_logged_in(self, course_url: str) -> None:
        page = self.open_course_page(course_url)
        try:
            risk = self.detect_risk_or_captcha(page)
            if risk:
                raise RuntimeError(f"Detected risk or captcha prompt: {risk}")
            if self.page_requires_login(page):
                raise RuntimeError("Current browser profile is not logged in")
            if not self._page_has_catalog_candidates(page):
                raise RuntimeError("Course page is visible but catalog entries were not detected")
        finally:
            page.close()

    def login(self, course_url: str) -> None:
        if self.headless:
            raise RuntimeError("Login requires a visible browser; headless must be false")
        page = self.open_course_page(course_url)
        try:
            print("请在浏览器中手动完成登录，然后回到终端按 Enter 继续校验。")
            input()
            page.goto(course_url, wait_until="domcontentloaded", timeout=45000)
            self._wait_for_ready_state(page)
            page.wait_for_timeout(1200)
            risk = self.detect_risk_or_captcha(page)
            if risk:
                raise RuntimeError(f"Detected risk or captcha prompt during login validation: {risk}")
            if self.page_requires_login(page):
                raise RuntimeError("登录校验失败：页面仍然要求登录")
            if not self._page_has_catalog_candidates(page):
                raise RuntimeError("登录校验失败：课程页未检测到可访问的目录项")
            print("登录校验通过，浏览器会话已保存到 state/browser_profile。")
        finally:
            page.close()

    def polite_pause(self) -> None:
        duration = random.uniform(self.delay_min, self.delay_max)
        self.logger.debug("Sleeping for %.2f seconds", duration)
        time.sleep(duration)

    def resolve_risk_interactively(self, page: Page) -> bool:
        if self.headless:
            return False
        print("检测到验证码或风控提示。请在浏览器中手动完成验证，然后回到终端按 Enter 继续。若无法处理，直接按 Ctrl+C 终止。")
        input()
        page.wait_for_timeout(1500)
        return self.detect_risk_or_captcha(page) is None
