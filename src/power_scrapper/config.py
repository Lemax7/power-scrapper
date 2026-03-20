"""Configuration dataclasses and constants for power_scrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

MIN_TITLE_LENGTH: int = 10
MIN_CONTENT_LENGTH: int = 200
MAX_ARTICLE_TEXT_LENGTH: int = 3000
DEFAULT_TIMEOUT: int = 10  # seconds
MIN_DELAY: int = 5  # seconds
MAX_DELAY: int = 15  # seconds

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ScraperConfig:
    """Top-level configuration for a scraping run."""

    query: str
    max_pages: int = 3
    language: str = "ru"
    country: str = "RU"
    debug: bool = False
    searxng_url: str | None = None
    output_dir: str = "./output"
    output_formats: list[str] = field(default_factory=lambda: ["excel", "json", "csv"])
    use_proxy: bool = False
    proxy_rotation: bool = True
    extract_articles: bool = True
    expand_with_titles: bool = False
    max_titles_to_expand: int = 5
    time_period: str | None = None
    max_concurrent_extractions: int = 10
    strict_search: bool = False
    only_strategies: list[str] | None = None  # e.g. ["google_search"] or ["google_news"]


@dataclass
class ArticleData:
    """Canonical representation of a scraped article.

    Compatible with the ``news_analytics`` pipeline.  The ``sentiment`` field
    from the predecessor is intentionally omitted -- sentiment analysis is
    handled by a separate module.

    ``source_type`` identifies where the article was obtained:
        "searxng", "google_search", "google_news", "yandex",
        "google_search_expansion", "from_media_list"
    """

    url: str
    title: str
    source: str
    date: datetime
    body: str = ""
    page: int = 1
    position: int = 0
    overall_position: int = 0
    article_text: str = ""
    source_type: str = "searxng"
