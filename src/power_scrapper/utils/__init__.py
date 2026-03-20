"""Utility helpers: date parsing, dedup, Punycode, URL building, caching, rate limiting."""

from power_scrapper.utils.cache import ResponseCache
from power_scrapper.utils.date_parser import DateParser
from power_scrapper.utils.dedup import (
    deduplicate_articles,
    filter_relevant,
    normalize_title_for_deduplication,
)
from power_scrapper.utils.punycode import PunycodeDecoder, extract_domain
from power_scrapper.utils.rate_limiter import AdaptiveRateLimiter
from power_scrapper.utils.small_media import SmallMediaLoader
from power_scrapper.utils.text_cleaning import clean_snippet
from power_scrapper.utils.url_builder import (
    YANDEX_REGIONS,
    build_google_news_url,
    build_google_search_url,
    build_site_query,
    build_yandex_search_url,
)

__all__ = [
    "AdaptiveRateLimiter",
    "DateParser",
    "PunycodeDecoder",
    "ResponseCache",
    "SmallMediaLoader",
    "YANDEX_REGIONS",
    "build_google_news_url",
    "build_google_search_url",
    "build_site_query",
    "build_yandex_search_url",
    "clean_snippet",
    "deduplicate_articles",
    "filter_relevant",
    "extract_domain",
    "normalize_title_for_deduplication",
]
