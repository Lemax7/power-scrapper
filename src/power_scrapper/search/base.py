"""Abstract base class for search strategies."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from power_scrapper.config import ArticleData, ScraperConfig

# Scrolling constants (ported from original scraper).
MAX_SCROLLS_PER_PAGE: int = 2
SCROLL_WAIT_SECONDS: float = 2.0

logger = logging.getLogger(__name__)


class ISearchStrategy(ABC):
    """Interface that every search backend (SearXNG, Google, Yandex, ...) implements."""

    @abstractmethod
    async def search(
        self,
        query: str,
        config: ScraperConfig,
        *,
        max_pages: int = 3,
    ) -> list[ArticleData]:
        """Execute a search and return a list of :class:`ArticleData` results."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Return ``True`` if the backend is reachable and ready."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name (e.g. ``"searxng"``)."""


class BrowserSearchStrategy(ISearchStrategy):
    """Base class for browser-based search strategies (Patchright).

    Provides common ``_ensure_browser()``, ``close()``, and ``is_available()``
    implementations shared by :class:`GoogleSearchStrategy`,
    :class:`GoogleNewsStrategy`, and :class:`YandexSearchStrategy`.
    """

    def __init__(self, *, patchright_context_manager: object | None = None) -> None:
        """Accept an optional async Patchright context manager for DI/testing."""
        self._pw_cm = patchright_context_manager
        self._pw: object | None = None
        self._browser: object | None = None

    async def is_available(self) -> bool:
        """Return True if patchright is importable."""
        try:
            import patchright  # noqa: F401

            return True
        except ImportError:
            return False

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

        if self._pw_cm is not None:
            # DI path (tests inject a mock context manager)
            self._pw = await self._pw_cm.__aenter__()
            self._browser = await self._pw.chromium.launch(headless=True)
            return

        from patchright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)  # type: ignore[union-attr]

    async def _scroll_page(self, page: object) -> None:
        """Scroll the page to trigger lazy-loaded content.

        Scrolls up to :data:`MAX_SCROLLS_PER_PAGE` times, waiting
        :data:`SCROLL_WAIT_SECONDS` between scrolls.  Stops early if the
        page height doesn't change (no new content loaded).
        """
        last_height = await page.evaluate("document.body.scrollHeight")  # type: ignore[union-attr]
        for _ in range(MAX_SCROLLS_PER_PAGE):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")  # type: ignore[union-attr]
            await asyncio.sleep(SCROLL_WAIT_SECONDS)
            new_height = await page.evaluate("document.body.scrollHeight")  # type: ignore[union-attr]
            if new_height == last_height:
                break
            last_height = new_height
