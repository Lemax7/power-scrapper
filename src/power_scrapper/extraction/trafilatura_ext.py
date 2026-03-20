"""Primary text extractor using trafilatura -- fast, HTTP-only."""

from __future__ import annotations

import asyncio
import logging

from power_scrapper.extraction.base import ITextExtractor

logger = logging.getLogger(__name__)


class TrafilaturaExtractor(ITextExtractor):
    """Primary extractor using trafilatura.

    Trafilatura is synchronous, so all calls are wrapped in
    :func:`asyncio.to_thread` to avoid blocking the event loop.
    """

    async def extract(self, url: str, html: str | None = None) -> str:  # noqa: D401
        try:
            import trafilatura  # noqa: PLC0415
        except ImportError:
            logger.debug("trafilatura is not installed -- skipping")
            return ""

        try:
            if html is None:
                html = await asyncio.to_thread(trafilatura.fetch_url, url)
                if not html:
                    return ""
            text: str | None = await asyncio.to_thread(
                trafilatura.extract,
                html,
                include_comments=False,
                include_tables=False,
            )
            return text or ""
        except Exception:
            logger.debug("trafilatura extraction failed for %s", url, exc_info=True)
            return ""

    @property
    def name(self) -> str:
        return "trafilatura"
