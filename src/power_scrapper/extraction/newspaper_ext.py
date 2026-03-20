"""Fallback text extractor using newspaper4k."""

from __future__ import annotations

import asyncio
import logging

from power_scrapper.extraction.base import ITextExtractor

logger = logging.getLogger(__name__)


class NewspaperExtractor(ITextExtractor):
    """Fallback extractor using newspaper4k.

    Good NLP features (authors, publish date) but slower than trafilatura.
    The library is synchronous -- calls are wrapped in :func:`asyncio.to_thread`.
    """

    async def extract(self, url: str, html: str | None = None) -> str:  # noqa: D401
        try:
            from newspaper import Article  # noqa: PLC0415
        except ImportError:
            logger.debug("newspaper4k is not installed -- skipping")
            return ""

        def _extract() -> str:
            article = Article(url)
            if html is not None:
                article.set_html(html)
                article.parse()
            else:
                article.download()
                article.parse()
            return article.text  # type: ignore[return-value]

        try:
            return await asyncio.to_thread(_extract)
        except Exception:
            logger.debug("newspaper4k extraction failed for %s", url, exc_info=True)
            return ""

    @property
    def name(self) -> str:
        return "newspaper4k"
