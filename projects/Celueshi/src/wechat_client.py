from __future__ import annotations

import random
import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Playwright, Request, Route, sync_playwright


BLOCK_URL_MARKERS = [
    "wappoc_appmsgcaptcha",
]
BLOCK_TEXT_MARKERS = [
    "环境异常",
    "验证码",
    "访问过于频繁",
    "请在微信客户端打开链接",
]
DELETED_TEXT_MARKERS = [
    "该内容已被发布者删除",
    "此内容已被发布者删除",
    "内容已被删除",
    "该内容因违规无法查看",
]


class WechatClient:
    def __init__(
        self,
        profile_dir: Path,
        logger,
        *,
        headless: bool = True,
        delay_min: float = 2.0,
        delay_max: float = 4.0,
        max_retries: int = 2,
    ) -> None:
        self.profile_dir = profile_dir
        self.logger = logger
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self._playwright: Playwright | None = None
        self.context: BrowserContext | None = None

    def __enter__(self) -> "WechatClient":
        self._playwright = sync_playwright().start()
        self._launch_context()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.context:
            self.context.close()
        if self._playwright:
            self._playwright.stop()

    def _launch_context(self) -> None:
        if not self._playwright:
            raise RuntimeError("Playwright has not started")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            viewport={"width": 1440, "height": 2200},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        self.context.route("**/*", self._route_request)

    def restart_context(self, reason: str) -> None:
        self.logger.info("重启浏览器上下文：%s", reason)
        if self.context:
            self.context.close()
        self._launch_context()

    def _route_request(self, route: Route, request: Request) -> None:
        if request.resource_type in {"image", "media", "font"}:
            route.abort()
            return
        route.continue_()

    def open_page(self, url: str, *, expected: str = "article") -> Page:
        if not self.context:
            raise RuntimeError("Browser context is not ready")
        page = self.context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        self._wait_for_page(page, expected)
        return page

    def _wait_for_page(self, page: Page, expected: str) -> None:
        selectors = ["#js_content", ".rich_media_content", "#activity-name", "body"]
        if expected == "directory":
            selectors = ["#js_content", ".rich_media_content", "body"]
        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=5000)
                break
            except Exception:
                continue

    def detect_block(self, page: Page) -> str | None:
        lowered_url = page.url.lower()
        for marker in BLOCK_URL_MARKERS:
            if marker in lowered_url:
                return marker
        text = page.evaluate("() => document.body ? document.body.innerText : ''")
        for marker in BLOCK_TEXT_MARKERS:
            if marker in text:
                return marker
        return None

    def detect_deleted(self, page: Page) -> str | None:
        text = page.evaluate("() => document.body ? document.body.innerText : ''")
        for marker in DELETED_TEXT_MARKERS:
            if marker in text:
                return marker
        return None

    def resolve_block_interactively(self, page: Page, target_url: str) -> bool:
        if self.headless:
            return False
        self.logger.warning("检测到微信校验页，请在浏览器中手动完成验证，然后回到终端按 Enter 继续。")
        input()
        page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        return self.detect_block(page) is None

    def polite_pause(self) -> None:
        time.sleep(random.uniform(self.delay_min, self.delay_max))
