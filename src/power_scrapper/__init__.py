"""power_scrapper -- news scraping with SearXNG, Playwright, and multi-source extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "0.1.0"

from power_scrapper.config import ArticleData, ScraperConfig
from power_scrapper.errors import (
    BotDetectedError,
    ExtractionError,
    ScraperError,
    SearchError,
)
from power_scrapper.log import setup_logging
from power_scrapper.scraper import Scraper

if TYPE_CHECKING:
    pass

__all__ = [
    "__version__",
    "ArticleData",
    "BotDetectedError",
    "ExtractionError",
    "Scraper",
    "ScraperConfig",
    "ScraperError",
    "SearchError",
    "scrape",
    "setup_logging",
]


async def scrape(query: str, **kwargs: object) -> list[ArticleData]:
    """One-call convenience function for programmatic use.

    All ``ScraperConfig`` fields are accepted as keyword arguments.

    Example::

        articles = await scrape("AI news", max_pages=2, searxng_url="http://localhost:8080")
    """
    config = ScraperConfig(query=query, **kwargs)  # type: ignore[arg-type]
    return await Scraper(config).run()
