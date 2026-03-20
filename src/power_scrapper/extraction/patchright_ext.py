"""Browser-based text extractor using Patchright for SPA/JS-heavy sites."""

from __future__ import annotations

import asyncio
import logging

from power_scrapper.extraction.base import ITextExtractor

logger = logging.getLogger(__name__)

# Max concurrent browser tabs to avoid resource exhaustion.
_MAX_CONCURRENT_PAGES = 3

# Timeout for page navigation in milliseconds.
_PAGE_TIMEOUT_MS = 30_000


class PatchrightExtractor(ITextExtractor):
    """Last-resort extractor that renders pages in headless Chromium.

    Useful for SPA/JS-heavy sites that return an empty shell over plain HTTP.
    Renders the page via Patchright, then feeds the resulting HTML to
    trafilatura for content extraction.

    The browser is lazily initialized on first use and shared across all
    extractions (one tab per URL).  Call :meth:`close` when done.
    """

    def __init__(self) -> None:
        self._pw: object | None = None
        self._browser: object | None = None
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PAGES)
        self._lock = asyncio.Lock()

    async def extract(self, url: str, html: str | None = None) -> str:  # noqa: D401
        try:
            import patchright  # noqa: F401
        except ImportError:
            logger.debug("patchright is not installed -- skipping")
            return ""

        try:
            import trafilatura  # noqa: F401
        except ImportError:
            logger.debug("trafilatura is not installed -- skipping patchright extractor")
            return ""

        async with self._semaphore:
            try:
                await self._ensure_browser()

                page = await self._browser.new_page()  # type: ignore[union-attr]
                try:
                    await page.goto(url, timeout=_PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
                    # Wait briefly for JS to render content.
                    await page.wait_for_timeout(2000)

                    rendered_html = await page.content()
                finally:
                    await page.close()

                if not rendered_html:
                    return ""

                result = trafilatura.extract(rendered_html, url=url)
                return result or ""

            except Exception:
                logger.debug("patchright extraction failed for %s", url, exc_info=True)
                return ""

    @property
    def name(self) -> str:
        return "patchright"

    async def close(self) -> None:
        """Shut down the browser and Patchright process."""
        if self._browser is not None:
            await self._browser.close()  # type: ignore[union-attr]
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()  # type: ignore[union-attr]
            self._pw = None

    async def _ensure_browser(self) -> None:
        """Lazily launch a headless Chromium via Patchright."""
        if self._browser is not None:
            return

        async with self._lock:
            # Double-check after acquiring lock.
            if self._browser is not None:
                return

            from patchright.async_api import async_playwright

            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)  # type: ignore[union-attr]
