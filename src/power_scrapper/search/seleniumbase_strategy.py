"""SeleniumBase CDP mode strategy for CAPTCHA-solving search.

Uses SeleniumBase CDP mode to spin up a stealth browser with built-in
CAPTCHA solving (``sb.solve_captcha()``), then optionally connects
Patchright via ``connect_over_cdp()`` for actual scraping.

Demonstrated bypassing Cloudflare Turnstile, Google reCAPTCHA, and
Akamai bot detection.  Only activated when simpler strategies fail
due to CAPTCHA.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from power_scrapper.config import ArticleData, ScraperConfig
from power_scrapper.search.base import ISearchStrategy

logger = logging.getLogger(__name__)


class SeleniumBaseCDPStrategy(ISearchStrategy):
    """CAPTCHA-solving search strategy using SeleniumBase CDP mode.

    Flow:
    1. SeleniumBase starts a stealth Chrome in CDP mode
    2. Navigates to search URL
    3. If CAPTCHA detected, calls ``sb.solve_captcha()``
    4. Extracts search results from rendered page

    This is a last-resort strategy -- only used when Patchright/Camoufox
    are blocked by CAPTCHAs.

    SeleniumBase is an optional dependency.
    """

    def __init__(self) -> None:
        self._available: bool | None = None

    async def search(
        self,
        query: str,
        config: ScraperConfig,
        *,
        max_pages: int = 3,
    ) -> list[ArticleData]:
        """Search Google with CAPTCHA solving via SeleniumBase CDP mode."""
        try:
            from seleniumbase import SB  # type: ignore[import-untyped]  # noqa: PLC0415
        except ImportError:
            logger.debug("seleniumbase is not installed -- skipping")
            return []

        articles: list[ArticleData] = []

        def _run_search() -> list[ArticleData]:
            results: list[ArticleData] = []
            with SB(uc=True, headless=True) as sb:
                for page_num in range(1, max_pages + 1):
                    start = (page_num - 1) * 10
                    url = (
                        f"https://www.google.com/search"
                        f"?q={query}"
                        f"&hl={config.language}"
                        f"&gl={config.country}"
                        f"&start={start}"
                    )
                    sb.open(url)

                    # Attempt CAPTCHA solving if needed.
                    import contextlib  # noqa: PLC0415

                    with contextlib.suppress(Exception):
                        sb.solve_captcha()

                    # Extract results from the page.
                    page_results = self._extract_results(sb, page_num, query)
                    results.extend(page_results)

                    if not page_results:
                        break

            return results

        try:
            articles = await asyncio.to_thread(_run_search)
        except Exception:
            logger.debug("SeleniumBase search failed for %r", query, exc_info=True)

        return articles

    @staticmethod
    def _extract_results(sb: object, page_num: int, query: str) -> list[ArticleData]:
        """Extract search results from the current SeleniumBase page."""
        results: list[ArticleData] = []

        try:
            # Standard Google result selectors.
            elements = sb.find_elements("css selector", "div.g")  # type: ignore[union-attr]

            for i, elem in enumerate(elements):
                try:
                    # Title
                    title_el = elem.find_element("css selector", "h3")
                    title = title_el.text if title_el else ""

                    # URL
                    link_el = elem.find_element("css selector", "a")
                    url = link_el.get_attribute("href") if link_el else ""

                    # Snippet
                    snippet = ""
                    try:
                        snippet_el = elem.find_element(
                            "css selector", "[data-sncf], .VwiC3b, .lEBKkf"
                        )
                        snippet = snippet_el.text if snippet_el else ""
                    except Exception:  # noqa: BLE001
                        pass

                    if url and title and url.startswith("http"):
                        from power_scrapper.utils.punycode import extract_domain  # noqa: PLC0415

                        results.append(
                            ArticleData(
                                url=url,
                                title=title,
                                source=extract_domain(url),
                                date=datetime.now(),
                                body=snippet,
                                source_type="seleniumbase_cdp",
                                page=page_num,
                                position=i + 1,
                            )
                        )
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            logger.debug("Failed to extract results from SeleniumBase page", exc_info=True)

        return results

    async def is_available(self) -> bool:
        """Return True if seleniumbase is importable."""
        if self._available is not None:
            return self._available

        try:
            import seleniumbase  # type: ignore[import-untyped]  # noqa: F401

            self._available = True
        except ImportError:
            self._available = False

        return self._available

    @property
    def name(self) -> str:  # noqa: D401
        """Strategy name."""
        return "seleniumbase_cdp"
