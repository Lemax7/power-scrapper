"""Fallback text extractor using readability-lxml (Mozilla reader-mode algorithm)."""

from __future__ import annotations

import asyncio
import logging

from power_scrapper.extraction.base import ITextExtractor

logger = logging.getLogger(__name__)


class ReadabilityExtractor(ITextExtractor):
    """Fallback extractor using readability-lxml.

    Applies Mozilla's reader-mode algorithm to simplify HTML, then strips
    remaining tags with BeautifulSoup.  If HTML is not provided, it is
    fetched via httpx.
    """

    async def extract(self, url: str, html: str | None = None) -> str:  # noqa: D401
        try:
            from readability import Document  # noqa: PLC0415
        except ImportError:
            logger.debug("readability-lxml is not installed -- skipping")
            return ""

        try:
            from bs4 import BeautifulSoup  # noqa: PLC0415
        except ImportError:
            logger.debug("beautifulsoup4 is not installed -- skipping")
            return ""

        # If no HTML supplied, fetch it
        if html is None:
            try:
                import httpx  # noqa: PLC0415

                async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    html = resp.text
            except Exception:
                logger.debug("readability: failed to fetch %s", url, exc_info=True)
                return ""

        def _extract(raw_html: str) -> str:
            doc = Document(raw_html)
            summary_html = doc.summary()
            soup = BeautifulSoup(summary_html, "html.parser")
            return soup.get_text(separator="\n", strip=True)

        try:
            return await asyncio.to_thread(_extract, html)
        except Exception:
            logger.debug("readability extraction failed for %s", url, exc_info=True)
            return ""

    @property
    def name(self) -> str:
        return "readability"
