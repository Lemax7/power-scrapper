"""power_scrapper -- next-generation news scraping with SearXNG, Playwright, and multi-source extraction."""

__version__ = "0.1.0"

from power_scrapper.config import ArticleData, ScraperConfig
from power_scrapper.errors import (
    BotDetectedError,
    ExtractionError,
    ScraperError,
    SearchError,
)
from power_scrapper.log import setup_logging

__all__ = [
    "__version__",
    "ArticleData",
    "BotDetectedError",
    "ExtractionError",
    "ScraperConfig",
    "ScraperError",
    "SearchError",
    "setup_logging",
]
