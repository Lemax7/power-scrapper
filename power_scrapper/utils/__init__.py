"""Utility helpers: date parsing, deduplication, Punycode decoding, URL building, small media."""

from power_scrapper.utils.date_parser import DateParser
from power_scrapper.utils.dedup import (
    deduplicate_articles,
    normalize_title_for_deduplication,
)
from power_scrapper.utils.punycode import PunycodeDecoder, extract_domain
from power_scrapper.utils.small_media import SmallMediaLoader
from power_scrapper.utils.url_builder import (
    YANDEX_REGIONS,
    build_google_news_url,
    build_google_search_url,
    build_site_query,
    build_yandex_search_url,
)

__all__ = [
    "DateParser",
    "PunycodeDecoder",
    "SmallMediaLoader",
    "YANDEX_REGIONS",
    "build_google_news_url",
    "build_google_search_url",
    "build_site_query",
    "build_yandex_search_url",
    "deduplicate_articles",
    "extract_domain",
    "normalize_title_for_deduplication",
]
