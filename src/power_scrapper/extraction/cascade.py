"""Cascade text extractor -- tries extractors in order, returns first success."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from power_scrapper.extraction.base import ITextExtractor
from power_scrapper.extraction.trafilatura_ext import TrafilaturaExtractor

if TYPE_CHECKING:
    from power_scrapper.config import ArticleData

logger = logging.getLogger(__name__)

# Minimum characters for a result to be considered "viable content".
_MIN_CONTENT_LENGTH = 50


class CascadeTextExtractor(ITextExtractor):
    """Tries extractors in priority order, returns the first successful result.

    Default cascade: trafilatura -> newspaper4k -> readability -> crawl4ai.
    Extractors whose underlying library is not installed are silently skipped
    during construction.
    """

    def __init__(self, extractors: list[ITextExtractor] | None = None) -> None:
        self._extractors = extractors if extractors is not None else self._default_extractors()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def _default_extractors() -> list[ITextExtractor]:
        """Build the default extractor list, skipping unavailable libraries."""
        extractors: list[ITextExtractor] = [TrafilaturaExtractor()]

        try:
            from power_scrapper.extraction.newspaper_ext import NewspaperExtractor  # noqa: PLC0415

            extractors.append(NewspaperExtractor())
        except ImportError:
            pass

        try:
            from power_scrapper.extraction.readability_ext import ReadabilityExtractor  # noqa: PLC0415, I001

            extractors.append(ReadabilityExtractor())
        except ImportError:
            pass

        try:
            from power_scrapper.extraction.crawl4ai_ext import Crawl4AIExtractor  # noqa: PLC0415

            extractors.append(Crawl4AIExtractor())
        except ImportError:
            pass

        try:
            from power_scrapper.extraction.patchright_ext import (
                PatchrightExtractor,  # noqa: PLC0415
            )

            extractors.append(PatchrightExtractor())
        except ImportError:
            pass

        return extractors

    # ------------------------------------------------------------------
    # ITextExtractor interface
    # ------------------------------------------------------------------

    async def extract(self, url: str, html: str | None = None) -> str:
        """Try each extractor in order; return the first viable result."""
        for extractor in self._extractors:
            try:
                result = await extractor.extract(url, html)
                if result and len(result.strip()) > _MIN_CONTENT_LENGTH:
                    logger.debug(
                        "Extracted %d chars with %s for %s",
                        len(result),
                        extractor.name,
                        url,
                    )
                    return result
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "Extractor %s failed for %s: %s",
                    extractor.name,
                    url,
                    exc,
                )
                continue
        return ""

    @property
    def name(self) -> str:
        return "cascade"

    # ------------------------------------------------------------------
    # Batch extraction
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close any extractors that hold resources (e.g. browser processes)."""
        for extractor in self._extractors:
            if hasattr(extractor, "close"):
                try:
                    await extractor.close()
                except Exception:  # noqa: BLE001
                    logger.debug("Failed to close extractor %s", extractor.name)

    async def extract_batch(
        self,
        articles: list[ArticleData],
        max_concurrent: int = 10,
    ) -> list[ArticleData]:
        """Extract text for multiple articles concurrently.

        Only articles whose ``article_text`` is empty are processed.
        Returns the same list with ``article_text`` populated where possible.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _extract_one(article: ArticleData) -> None:
            if article.article_text:
                return
            async with semaphore:
                text = await self.extract(article.url)
                article.article_text = text

        tasks = [asyncio.create_task(_extract_one(a)) for a in articles]
        await asyncio.gather(*tasks, return_exceptions=True)

        extracted_count = sum(1 for a in articles if a.article_text)
        logger.info(
            "Extraction complete: %d/%d articles have text",
            extracted_count,
            len(articles),
        )
        return articles
