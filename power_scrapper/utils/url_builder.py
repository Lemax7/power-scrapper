"""URL construction helpers for various search engines."""

from __future__ import annotations

from urllib.parse import urlencode

from power_scrapper.config import ScraperConfig


def build_google_search_url(query: str, config: ScraperConfig, *, page: int = 0) -> str:
    """Build Google Search URL with language, country, time period."""
    params: dict[str, str | int] = {
        "q": query,
        "hl": config.language,
        "gl": config.country,
        "num": 10,
    }
    if page > 0:
        params["start"] = page * 10
    if config.time_period:
        params["tbs"] = f"qdr:{config.time_period}"
    return f"https://www.google.com/search?{urlencode(params)}"


def build_google_news_url(query: str, config: ScraperConfig, *, page: int = 0) -> str:
    """Build Google News tab URL."""
    params: dict[str, str | int] = {
        "q": query,
        "hl": config.language,
        "gl": config.country,
        "tbm": "nws",
    }
    if page > 0:
        params["start"] = page * 10
    return f"https://www.google.com/search?{urlencode(params)}"


def build_yandex_search_url(query: str, config: ScraperConfig, *, page: int = 0) -> str:
    """Build Yandex search URL."""
    params: dict[str, str | int] = {
        "text": query,
        "lr": 213,  # Moscow by default
    }
    if page > 0:
        params["p"] = page
    return f"https://yandex.ru/search/?{urlencode(params)}"


def build_site_query(base_query: str, domain: str) -> str:
    """Add site: operator to query."""
    return f"{base_query} site:{domain}"
