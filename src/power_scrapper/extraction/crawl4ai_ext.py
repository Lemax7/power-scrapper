"""Optional text extractor using crawl4ai v0.8.x for clean markdown output.

Features over basic AsyncWebCrawler.arun():
- CSS selector targeting for article content regions
- Shadow DOM flattening for modern component-based sites
- Consent popup removal (GDPR banners)
- Anti-bot detection enabled
- JavaScript wait conditions for SPA-rendered content
- Clean markdown output (LLM-friendly)

No LLM extraction is used -- downstream OpenClaw agents handle analysis.
"""

from __future__ import annotations

import logging

from power_scrapper.extraction.base import ITextExtractor

logger = logging.getLogger(__name__)

# Common CSS selectors for article content regions, tried in order.
_ARTICLE_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    ".post-content",
    ".article-content",
    ".article-body",
    ".entry-content",
    ".story-body",
    "#article-body",
    ".content-body",
]


class Crawl4AIExtractor(ITextExtractor):
    """Extractor using crawl4ai v0.8.x with advanced configuration.

    Returns markdown-formatted article text.  Entirely optional -- if
    crawl4ai is not installed the extractor silently returns an empty string.
    No LLM is required.
    """

    async def extract(self, url: str, html: str | None = None) -> str:  # noqa: D401
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig  # noqa: PLC0415
        except ImportError:
            # Fall back to legacy API if v0.8.x not installed.
            return await self._extract_legacy(url, html)

        try:
            browser_config = BrowserConfig(
                headless=True,
                text_mode=True,  # Faster: blocks images/media
            )

            run_config = CrawlerRunConfig(
                # Target article content regions.
                css_selector=", ".join(_ARTICLE_SELECTORS),
                # Strip noise tags.
                excluded_tags=["script", "style", "nav", "footer", "header", "aside"],
                # Remove external links from output.
                exclude_external_links=True,
                # Wait for content to render (SPA support).
                wait_for="css:article, css:main, css:body",
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                if result and result.success:
                    # Prefer fit_markdown (cleaned) over raw markdown.
                    md = getattr(result, "fit_markdown", None) or getattr(
                        result, "markdown", None
                    )
                    if md:
                        return str(md)
                return ""
        except Exception:
            logger.debug("crawl4ai extraction failed for %s", url, exc_info=True)
            return ""

    async def _extract_legacy(self, url: str, html: str | None = None) -> str:
        """Legacy extraction for crawl4ai versions before 0.8."""
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
            logger.debug("crawl4ai legacy extraction failed for %s", url, exc_info=True)
            return ""

    @property
    def name(self) -> str:
        return "crawl4ai"
