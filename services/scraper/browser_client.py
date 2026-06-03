# services/scraper/browser_client — Browser Use integration with fallback
"""Thin wrapper around Browser Use for JS-heavy scraping.
Falls back to aiohttp if Browser Use is unavailable or fails."""

import asyncio
import logging
import os
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BROWSER_USE_AVAILABLE = False
_BROWSER_INSTANCE = None
_BROWSER_LOCK = asyncio.Lock()


def _check_browser_use() -> bool:
    """Check if browser-use is importable."""
    global _BROWSER_USE_AVAILABLE
    if _BROWSER_USE_AVAILABLE:
        return True
    try:
        import browser_use  # noqa: F401
        _BROWSER_USE_AVAILABLE = True
        return True
    except ImportError:
        logger.info("browser-use not installed; using aiohttp fallback for scraping")
        return False


class BrowserClient:
    """Wrapper for Browser Use / Playwright browser automation.

    Used selectively for:
    - JS-heavy sites (ProductHunt, IndieHackers, etc.)
    - Pages requiring interaction (click, scroll, pagination)
    - Anti-bot challenges that need real browser fingerprints

    Falls back to aiohttp + BeautifulSoup when Browser Use is unavailable.
    """

    def __init__(self, headless: bool = True, timeout: int = 30):
        self.headless = headless
        self.timeout = timeout
        self._browser = None
        self._context = None

    async def _get_browser(self):
        """Lazy-init the Playwright browser via Browser Use."""
        if self._browser:
            return self._browser

        if not _check_browser_use():
            raise RuntimeError("browser-use not available")

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        return self._browser

    async def _get_context(self):
        """Get or create a browser context with realistic fingerprint."""
        browser = await self._get_browser()
        if self._context is None or self._context.is_closed():
            self._context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="America/New_York",
            )
        return self._context

    async def fetch_page(
        self,
        url: str,
        wait_for: Optional[str] = None,
        scroll: bool = False,
        max_wait_ms: int = 5000,
    ) -> str:
        """Fetch a fully-rendered page as HTML.

        Args:
            url: Page URL.
            wait_for: Optional CSS selector to wait for before returning.
            scroll: Whether to scroll to bottom to trigger lazy loading.
            max_wait_ms: Max time to wait for selector/network idle.

        Returns:
            Rendered HTML string.
        """
        async with _BROWSER_LOCK:
            context = await self._get_context()
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)

                if wait_for:
                    try:
                        await page.wait_for_selector(wait_for, timeout=max_wait_ms)
                    except Exception:
                        logger.debug(f"[browser] Selector not found: {wait_for} on {url}")

                if scroll:
                    await self._scroll_page(page)

                # Small delay to let any final JS run
                await asyncio.sleep(0.5)

                return await page.content()

            finally:
                await page.close()

    async def _scroll_page(self, page, steps: int = 5, delay_ms: int = 300):
        """Scroll page incrementally to trigger lazy loading."""
        for _ in range(steps):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(delay_ms / 1000)

    async def extract_with_task(
        self,
        url: str,
        task_description: str,
    ) -> dict:
        """Use Browser Use agent to extract structured data from a page.

        Args:
            url: Page URL.
            task_description: Natural-language instruction for the agent.

        Returns:
            Dict with extracted data, or empty dict on failure.
        """
        if not _check_browser_use():
            return {}

        try:
            from browser_use import Agent, Browser, ChatBrowserUse

            llm = ChatBrowserUse()
            browser = Browser(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )

            agent = Agent(
                task=f"Go to {url}. {task_description} Return the result as JSON.",
                llm=llm,
                browser=browser,
            )

            result = await agent.run()
            await browser.close()

            if isinstance(result, dict):
                return result
            return {"raw": str(result)}

        except Exception as e:
            logger.warning(f"[browser] Agent extraction failed for {url}: {e}")
            return {}

    async def close(self):
        """Close browser resources."""
        try:
            if self._context and not self._context.is_closed():
                await self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if hasattr(self, "_playwright") and self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._context = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class BrowserAwareProvider:
    """Mixin for providers that can use Browser Client for JS-heavy pages."""

    browser_client: Optional[BrowserClient] = None
    use_browser_for: list = field(default_factory=list)  # domain patterns

    def _should_use_browser(self, url: str) -> bool:
        """Check if URL matches patterns that need a real browser."""
        if not self.browser_client:
            return False
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        for pattern in self.use_browser_for:
            if pattern.lower() in domain:
                return True
        return False
