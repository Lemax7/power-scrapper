"""Yandex search strategy via Patchright browser automation."""

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
from power_scrapper.utils.text_cleaning import clean_snippet
from power_scrapper.utils.url_builder import (
    YANDEX_REGIONS,  # noqa: F401 -- re-exported for backward compatibility
    build_yandex_search_url,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bot detection for Yandex
# ---------------------------------------------------------------------------

YANDEX_BOT_PHRASES: list[str] = [
    "я не робот",
    "вы не робот",
    "i'm not a robot",
    "подозрительный трафик",
    "suspicious traffic",
    "подтвердите, что вы не робот",
    "confirm you are not a robot",
    "captcha",
    "showcaptcha",
]

YANDEX_CAPTCHA_SELECTORS: list[str] = [
    "div.CheckboxCaptcha",
    "div.AdvancedCaptcha",
    "form[action*='showcaptcha']",
    "img.AdvancedCaptcha-Image",
    "input.CheckboxCaptcha-Button",
]

# CSS selectors for Yandex search results (they change, try multiple)
_YANDEX_RESULT_SELECTORS: list[str] = [
    "li.serp-item",
    "div.organic",
    "div[data-cid]",
]


def check_yandex_bot_detection(content: str) -> bool:
    """Return True if the page content contains Yandex bot-detection signals."""
    content_lower = content.lower()
    return any(phrase in content_lower for phrase in YANDEX_BOT_PHRASES)


class YandexSearchStrategy(BrowserSearchStrategy):
    """Yandex search results via Patchright browser automation."""

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
            url = build_yandex_search_url(query, config, page_num=page_num)
            logger.debug("Yandex request: %s", url)

            page = await self._browser.new_page()  # type: ignore[union-attr]
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

                content = await page.content()

                # Check for captcha elements first (more reliable)
                for selector in YANDEX_CAPTCHA_SELECTORS:
                    try:
                        captcha_el = await page.query_selector(selector)
                        if captcha_el:
                            raise BotDetectedError("Yandex CAPTCHA detected")
                    except BotDetectedError:
                        raise
                    except Exception:  # noqa: BLE001
                        pass

                if check_yandex_bot_detection(content):
                    raise BotDetectedError("Yandex detected bot activity")

                await self._scroll_page(page)
                articles = await self._parse_results(page, page_num + 1)
                all_articles.extend(articles)

                if not articles:
                    logger.info("Yandex page %d returned 0 results, stopping", page_num + 1)
                    break
            except BotDetectedError:
                raise
            except Exception as exc:
                raise BrowserSearchError(f"Yandex failed on page {page_num + 1}: {exc}") from exc
            finally:
                await page.close()

        # Calculate overall_position across all pages.
        for i, article in enumerate(all_articles):
            article.overall_position = i + 1
        return all_articles

    @property
    def name(self) -> str:  # noqa: D401
        return "yandex"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _parse_results(self, page: object, page_number: int) -> list[ArticleData]:
        articles: list[ArticleData] = []

        result_elements = []
        for selector in _YANDEX_RESULT_SELECTORS:
            try:
                result_elements = await page.query_selector_all(selector)  # type: ignore[union-attr]
                if result_elements:
                    logger.debug(
                        "Yandex selector %r matched %d elements",
                        selector,
                        len(result_elements),
                    )
                    break
            except Exception:  # noqa: BLE001
                continue

        if not result_elements:
            logger.warning("Yandex: no result elements found on page %d", page_number)
            return articles

        for idx, elem in enumerate(result_elements):
            try:
                article = await self._parse_single_result(elem, page_number, idx + 1)
                if article is not None:
                    articles.append(article)
            except Exception:  # noqa: BLE001
                logger.debug("Yandex: failed to parse result %d on page %d", idx, page_number)

        logger.info("Yandex page %d: %d results extracted", page_number, len(articles))
        return articles

    async def _parse_single_result(
        self,
        elem: object,
        page_number: int,
        position: int,
    ) -> ArticleData | None:
        # Extract URL — try h2 a[href] first, then any a[href]
        link_el = None
        for link_sel in ("h2 a[href]", ".OrganicTitle a[href]", "a[href]"):
            link_el = await elem.query_selector(link_sel)  # type: ignore[union-attr]
            if link_el:
                break
        if link_el is None:
            return None

        href = await link_el.get_attribute("href")
        if not href or "yandex." in href:
            return None

        # Extract title
        title = ""
        for title_sel in (
            "h2",
            ".OrganicTitle-LinkText",
            ".organic__title-part",
            ".OrganicTitleContentSpan",
        ):
            title_el = await elem.query_selector(title_sel)  # type: ignore[union-attr]
            if title_el:
                title = (await title_el.inner_text()).strip()
                if title:
                    break
        if len(title) < MIN_TITLE_LENGTH:
            return None

        # Extract source
        source = ""
        for src_sel in (".Path", ".OrganicUrl", ".organic__path", ".Organic-Path"):
            src_el = await elem.query_selector(src_sel)  # type: ignore[union-attr]
            if src_el:
                source = (await src_el.inner_text()).strip()
                if source:
                    break
        if not source:
            source = _extract_domain(href)

        # Extract snippet/body
        body = ""
        for body_sel in (".OrganicText", ".TextContainer", ".organic__content-wrapper", ".Typo"):
            body_el = await elem.query_selector(body_sel)  # type: ignore[union-attr]
            if body_el:
                body = (await body_el.inner_text()).strip()
                if body:
                    break

        # Date — Yandex sometimes shows dates in results
        date = datetime.now()
        for date_sel in (".organic__subtitle", ".OrganicSubtitle", ".Organic-Subtitle"):
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
            body=clean_snippet(body),
            source_type="yandex",
            page=page_number,
            position=position,
        )
