"""Optional text extractor using crawl4ai for clean markdown output."""

from __future__ import annotations

import logging

from power_scrapper.extraction.base import ITextExtractor

logger = logging.getLogger(__name__)


class Crawl4AIExtractor(ITextExtractor):
    """Optional extractor using crawl4ai.

    Returns markdown-formatted article text.  Entirely optional -- if
    crawl4ai is not installed the extractor silently returns an empty string.
    No LLM is required.
    """

    async def extract(self, url: str, html: str | None = None) -> str:  # noqa: D401
        try:
            from crawl4ai import AsyncWebCrawler  # noqa: PLC0415
        except ImportError:
            logger.debug("crawl4ai is not installed -- skipping")
            return ""

        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url)
                if result and result.markdown:
                    return str(result.markdown)
                return ""
        except Exception:
            logger.debug("crawl4ai extraction failed for %s", url, exc_info=True)
            return ""

    @property
    def name(self) -> str:
        return "crawl4ai"
