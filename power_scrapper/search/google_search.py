"""Google Search DOM parsing strategy via Patchright browser automation."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from power_scrapper.config import MAX_DELAY, MIN_DELAY, MIN_TITLE_LENGTH, ArticleData, ScraperConfig
from power_scrapper.errors import BotDetectedError, BrowserSearchError
from power_scrapper.search.base import BrowserSearchStrategy
from power_scrapper.utils import DateParser
from power_scrapper.utils.punycode import extract_domain as _extract_domain
from power_scrapper.utils.url_builder import build_google_search_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bot detection phrases (ported from reference scraper_core.py)
# ---------------------------------------------------------------------------

BOT_DETECTION_PHRASES: list[str] = [
    "подозрительный трафик",
    "suspicious traffic",
    "необычный трафик",
    "unusual traffic",
    "verify you are human",
    "подтвердите, что вы человек",
    "solve the captcha",
    "решите капчу",
    "our systems have detected unusual traffic",
    "наши системы обнаружили необычный трафик",
    "you are not a robot",
    "вы не робот",
    "i'm not a robot",
    "я не робот",
]

CAPTCHA_SELECTORS: list[str] = [
    "div[id*='captcha']",
    "div[class*='captcha']",
    "div[id*='recaptcha']",
    "div[class*='recaptcha']",
    "#captcha",
    ".captcha",
    ".g-recaptcha",
    "iframe[src*='recaptcha']",
]

# Google system messages to filter out (not real articles)
GOOGLE_SYSTEM_MESSAGES: list[str] = [
    "по запросу",
    "nothing found",
    "no results",
    "ничего не найдено",
    "результатов не найдено",
    "другие также ищут",
    "people also search",
    "related searches",
]

# CSS selectors to try for extracting result items (Google changes these frequently)
_RESULT_SELECTORS: list[str] = [
    "div[jscontroller][data-hveid][data-ved][lang]",
    "div.g",
    "[data-snc]",
    "div[data-hveid] :has(> h3)",
]


def check_bot_detection(content: str) -> bool:
    """Return True if the page content contains bot-detection signals."""
    content_lower = content.lower()
    return any(phrase in content_lower for phrase in BOT_DETECTION_PHRASES)


def _is_google_system_message(title: str) -> bool:
    """Return True if *title* looks like a Google system message rather than a real result."""
    title_lower = title.lower()
    return any(msg in title_lower for msg in GOOGLE_SYSTEM_MESSAGES)


class GoogleSearchStrategy(BrowserSearchStrategy):
    """Google Search results via Patchright browser automation."""

    # ------------------------------------------------------------------
    # ISearchStrategy
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        config: ScraperConfig,
        *,
        max_pages: int = 3,
    ) -> list[ArticleData]:
        await self._ensure_browser()
        all_articles: list[ArticleData] = []

        for page_num in range(max_pages):
            start = page_num * 10
            url = build_google_search_url(query, config, start=start)
            logger.debug("GoogleSearch request: %s", url)

            page = await self._browser.new_page()  # type: ignore[union-attr]
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

                content = await page.content()
                if check_bot_detection(content):
                    raise BotDetectedError("Google detected bot activity")

                articles = await self._parse_results(page, page_num + 1)
                all_articles.extend(articles)

                if not articles:
                    logger.info("GoogleSearch page %d returned 0 results, stopping", page_num + 1)
                    break
            except BotDetectedError:
                raise
            except Exception as exc:
                raise BrowserSearchError(
                    f"GoogleSearch failed on page {page_num + 1}: {exc}"
                ) from exc
            finally:
                await page.close()

        return all_articles

    @property
    def name(self) -> str:  # noqa: D401
        return "google_search"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _parse_results(self, page: object, page_number: int) -> list[ArticleData]:
        """Extract search result items from a Google Search results page."""
        articles: list[ArticleData] = []

        # Try multiple selector strategies because Google frequently changes its DOM.
        result_elements = []
        for selector in _RESULT_SELECTORS:
            try:
                result_elements = await page.query_selector_all(selector)  # type: ignore[union-attr]
                if result_elements:
                    logger.debug(
                        "GoogleSearch selector %r matched %d elements",
                        selector,
                        len(result_elements),
                    )
                    break
            except Exception:  # noqa: BLE001
                continue

        if not result_elements:
            logger.warning("GoogleSearch: no result elements found on page %d", page_number)
            return articles

        for idx, elem in enumerate(result_elements):
            try:
                article = await self._parse_single_result(elem, page_number, idx + 1)
                if article is not None:
                    articles.append(article)
            except Exception:  # noqa: BLE001
                logger.debug("GoogleSearch: failed to parse result %d on page %d", idx, page_number)

        logger.info("GoogleSearch page %d: %d results extracted", page_number, len(articles))
        return articles

    async def _parse_single_result(
        self,
        elem: object,
        page_number: int,
        position: int,
    ) -> ArticleData | None:
        """Parse a single search result element into an ArticleData or return None."""
        # Extract URL
        link_el = await elem.query_selector("a[href]")  # type: ignore[union-attr]
        if link_el is None:
            return None
        href = await link_el.get_attribute("href")
        if not href or "google.com" in href:
            return None

        # Extract title
        title_el = await elem.query_selector("h3")  # type: ignore[union-attr]
        title = (await title_el.inner_text()).strip() if title_el else ""
        if len(title) < MIN_TITLE_LENGTH:
            return None
        if _is_google_system_message(title):
            return None

        # Extract source
        source = _extract_domain(href)

        # Extract snippet/body — try several selectors
        body = ""
        for body_sel in ("[data-sncf='1'] span", "div[data-sncf] span", ".VwiC3b", "span.st"):
            body_el = await elem.query_selector(body_sel)  # type: ignore[union-attr]
            if body_el:
                body = (await body_el.inner_text()).strip()
                if body:
                    break

        # Extract date — look for cite or span elements with date-like content
        date = datetime.now()
        for date_sel in ("span.LEwnzc", "span.MUxGbd", "cite + span"):
            date_el = await elem.query_selector(date_sel)  # type: ignore[union-attr]
            if date_el:
                date_text = (await date_el.inner_text()).strip()
                if date_text:
                    date = DateParser.parse_date(date_text)
                    break

        return ArticleData(
            url=href,
            title=title,
            source=source,
            date=date,
            body=body,
            source_type="google_search",
            page=page_number,
            position=position,
        )
