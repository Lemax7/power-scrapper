"""URL construction helpers for various search engines."""

from __future__ import annotations

from urllib.parse import quote_plus

from power_scrapper.config import ScraperConfig

# Yandex region codes (country -> lr parameter).
YANDEX_REGIONS: dict[str, int] = {
    "RU": 213,  # Moscow
    "UA": 143,  # Kiev
    "BY": 157,  # Minsk
    "KZ": 162,  # Almaty
    "US": 84,  # USA
    "GB": 10393,  # London
}


def build_google_search_url(
    query: str,
    config: ScraperConfig,
    *,
    page: int = 0,
    start: int | None = None,
) -> str:
    """Build Google Search URL with language, country, time period.

    Accepts either ``page`` (0-based page number, offset computed as
    ``page * 10``) or ``start`` (raw offset).  When ``start`` is given
    explicitly it is always included in the URL.  When using ``page``,
    the ``start`` parameter is omitted for page 0.
    """
    params = f"q={quote_plus(query)}&hl={config.language}&gl={config.country}"
    if start is not None:
        params += f"&start={start}"
    elif page > 0:
        params += f"&start={page * 10}"
    params += "&num=10"
    if config.time_period:
        params += f"&tbs=qdr:{config.time_period}"
    return f"https://www.google.com/search?{params}"


def build_google_news_url(
    query: str,
    config: ScraperConfig,
    *,
    page: int = 0,
    start: int | None = None,
) -> str:
    """Build Google News tab URL.

    Accepts either ``page`` (0-based page number, offset computed as
    ``page * 10``) or ``start`` (raw offset).  When ``start`` is given
    explicitly it is always included in the URL.  When using ``page``,
    the ``start`` parameter is omitted for page 0.
    """
    params = f"q={quote_plus(query)}&hl={config.language}&gl={config.country}&tbm=nws"
    if start is not None:
        params += f"&start={start}"
    elif page > 0:
        params += f"&start={page * 10}"
    if config.time_period:
        params += f"&tbs=qdr:{config.time_period}"
    return f"https://www.google.com/search?{params}"


def build_yandex_search_url(
    query: str,
    config: ScraperConfig,
    *,
    page: int = 0,
    page_num: int | None = None,
) -> str:
    """Build Yandex search URL.

    Accepts either ``page`` or ``page_num`` (both 0-based page numbers).
    ``page_num`` takes precedence when both are provided.  When
    ``page_num`` is given explicitly it is always included in the URL.
    When using ``page``, the ``p`` parameter is omitted for page 0.
    Uses the ``YANDEX_REGIONS`` mapping to resolve the ``lr`` parameter
    from ``config.country``.
    """
    lr = YANDEX_REGIONS.get(config.country, 213)
    params = f"text={quote_plus(query)}&lr={lr}"
    if page_num is not None:
        params += f"&p={page_num}"
    elif page > 0:
        params += f"&p={page}"
    return f"https://yandex.ru/search/?{params}"


def build_site_query(base_query: str, domain: str) -> str:
    """Add site: operator to query."""
    return f"{base_query} site:{domain}"
