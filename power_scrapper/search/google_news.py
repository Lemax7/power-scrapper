"""Google News tab search strategy via Patchright browser automation."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from power_scrapper.config import MAX_DELAY, MIN_DELAY, MIN_TITLE_LENGTH, ArticleData, ScraperConfig
from power_scrapper.errors import BotDetectedError, BrowserSearchError
from power_scrapper.search.base import BrowserSearchStrategy
from power_scrapper.search.google_search import check_bot_detection
from power_scrapper.utils import DateParser
from power_scrapper.utils.punycode import extract_domain as _extract_domain
from power_scrapper.utils.url_builder import build_google_news_url

logger = logging.getLogger(__name__)

# CSS selectors for Google News tab results
_NEWS_RESULT_SELECTORS: list[str] = [
    "div[data-news-cluster-id]",
    "div.SoaBEf",
    "div.dbsr",
]


class GoogleNewsStrategy(BrowserSearchStrategy):
    """Google News tab results via Patchright browser automation."""

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
            url = build_google_news_url(query, config, start=start)
            logger.debug("GoogleNews request: %s", url)

            page = await self._browser.new_page()  # type: ignore[union-attr]
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

                content = await page.content()
                if check_bot_detection(content):
                    raise BotDetectedError("Google News detected bot activity")

                articles = await self._parse_results(page, page_num + 1)
                all_articles.extend(articles)

                if not articles:
                    logger.info("GoogleNews page %d returned 0 results, stopping", page_num + 1)
                    break
            except BotDetectedError:
                raise
            except Exception as exc:
                raise BrowserSearchError(
                    f"GoogleNews failed on page {page_num + 1}: {exc}"
                ) from exc
            finally:
                await page.close()

        return all_articles

    @property
    def name(self) -> str:  # noqa: D401
        return "google_news"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _parse_results(self, page: object, page_number: int) -> list[ArticleData]:
        articles: list[ArticleData] = []

        result_elements = []
        for selector in _NEWS_RESULT_SELECTORS:
            try:
                result_elements = await page.query_selector_all(selector)  # type: ignore[union-attr]
                if result_elements:
                    logger.debug(
                        "GoogleNews selector %r matched %d elements",
                        selector,
                        len(result_elements),
                    )
                    break
            except Exception:  # noqa: BLE001
                continue

        if not result_elements:
            logger.warning("GoogleNews: no result elements found on page %d", page_number)
            return articles

        for idx, elem in enumerate(result_elements):
            try:
                article = await self._parse_single_result(elem, page_number, idx + 1)
                if article is not None:
                    articles.append(article)
            except Exception:  # noqa: BLE001
                logger.debug("GoogleNews: failed to parse result %d on page %d", idx, page_number)

        logger.info("GoogleNews page %d: %d results extracted", page_number, len(articles))
        return articles

    async def _parse_single_result(
        self,
        elem: object,
        page_number: int,
        position: int,
    ) -> ArticleData | None:
        # Extract URL
        link_el = await elem.query_selector("a[href]")  # type: ignore[union-attr]
        if link_el is None:
            return None
        href = await link_el.get_attribute("href")
        if not href or "google.com" in href:
            return None

        # Extract title — news results use div[role='heading'] or a text
        title = ""
        for title_sel in ("div[role='heading']", "h3", "a"):
            title_el = await elem.query_selector(title_sel)  # type: ignore[union-attr]
            if title_el:
                title = (await title_el.inner_text()).strip()
                if title:
                    break
        if len(title) < MIN_TITLE_LENGTH:
            return None

        # Extract source — g-img span or .CEMjEf span
        source = ""
        for src_sel in ("g-img + span", ".CEMjEf span", "span.WF4CUc", ".NUnG9d span"):
            src_el = await elem.query_selector(src_sel)  # type: ignore[union-attr]
            if src_el:
                source = (await src_el.inner_text()).strip()
                if source:
                    break
        if not source:
            source = _extract_domain(href)

        # Extract date — time element or span with date-like content
        date = datetime.now()
        for date_sel in ("time", "span.WG9SHc", "span.r0bn4c", "span.OSrXXb"):
            date_el = await elem.query_selector(date_sel)  # type: ignore[union-attr]
            if date_el:
                # Try datetime attribute first (on <time> elements)
                datetime_attr = await date_el.get_attribute("datetime")
                if datetime_attr:
                    date = DateParser.parse_date(datetime_attr)
                    break
                date_text = (await date_el.inner_text()).strip()
                if date_text:
                    date = DateParser.parse_date(date_text)
                    break

        # Body/snippet is usually absent in Google News tab, but try
        body = ""
        for body_sel in (".GI74Re", ".Y3v8qd", ".st"):
            body_el = await elem.query_selector(body_sel)  # type: ignore[union-attr]
            if body_el:
                body = (await body_el.inner_text()).strip()
                if body:
                    break

        return ArticleData(
            url=href,
            title=title,
            source=source,
            date=date,
            body=body,
            source_type="google_news",
            page=page_number,
            position=position,
        )
