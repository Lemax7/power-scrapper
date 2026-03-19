"""Tests for power_scrapper.utils.url_builder."""

from __future__ import annotations

from power_scrapper.config import ScraperConfig
from power_scrapper.utils.url_builder import (
    build_google_news_url,
    build_google_search_url,
    build_site_query,
    build_yandex_search_url,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_config(**overrides: object) -> ScraperConfig:
    """Create a ScraperConfig with sensible defaults, applying overrides."""
    defaults = {"query": "test", "language": "ru", "country": "RU"}
    defaults.update(overrides)  # type: ignore[arg-type]
    return ScraperConfig(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_google_search_url
# ---------------------------------------------------------------------------


class TestBuildGoogleSearchUrl:
    def test_basic_url(self) -> None:
        config = _default_config()
        url = build_google_search_url("AI news", config)
        assert url.startswith("https://www.google.com/search?")
        assert "q=AI+news" in url
        assert "hl=ru" in url
        assert "gl=RU" in url
        assert "num=10" in url

    def test_page_zero_has_no_start(self) -> None:
        config = _default_config()
        url = build_google_search_url("test", config, page=0)
        assert "start=" not in url

    def test_page_two(self) -> None:
        config = _default_config()
        url = build_google_search_url("test", config, page=2)
        assert "start=20" in url

    def test_time_period(self) -> None:
        config = _default_config(time_period="d")
        url = build_google_search_url("test", config)
        assert "tbs=qdr%3Ad" in url or "tbs=qdr:d" in url

    def test_no_time_period(self) -> None:
        config = _default_config(time_period=None)
        url = build_google_search_url("test", config)
        assert "tbs=" not in url

    def test_english_config(self) -> None:
        config = _default_config(language="en", country="US")
        url = build_google_search_url("test query", config)
        assert "hl=en" in url
        assert "gl=US" in url

    def test_cyrillic_query(self) -> None:
        config = _default_config()
        url = build_google_search_url("новости ИИ", config)
        assert "q=" in url
        # The Cyrillic should be URL-encoded
        assert "новости" not in url  # must be encoded


# ---------------------------------------------------------------------------
# build_google_news_url
# ---------------------------------------------------------------------------


class TestBuildGoogleNewsUrl:
    def test_basic_url(self) -> None:
        config = _default_config()
        url = build_google_news_url("AI news", config)
        assert url.startswith("https://www.google.com/search?")
        assert "q=AI+news" in url
        assert "tbm=nws" in url
        assert "hl=ru" in url
        assert "gl=RU" in url

    def test_page_zero_has_no_start(self) -> None:
        config = _default_config()
        url = build_google_news_url("test", config, page=0)
        assert "start=" not in url

    def test_page_three(self) -> None:
        config = _default_config()
        url = build_google_news_url("test", config, page=3)
        assert "start=30" in url


# ---------------------------------------------------------------------------
# build_yandex_search_url
# ---------------------------------------------------------------------------


class TestBuildYandexSearchUrl:
    def test_basic_url(self) -> None:
        config = _default_config()
        url = build_yandex_search_url("AI news", config)
        assert url.startswith("https://yandex.ru/search/?")
        assert "text=AI+news" in url
        assert "lr=213" in url

    def test_page_zero_has_no_p(self) -> None:
        config = _default_config()
        url = build_yandex_search_url("test", config, page=0)
        assert "p=" not in url

    def test_page_one(self) -> None:
        config = _default_config()
        url = build_yandex_search_url("test", config, page=1)
        assert "p=1" in url


# ---------------------------------------------------------------------------
# build_site_query
# ---------------------------------------------------------------------------


class TestBuildSiteQuery:
    def test_simple(self) -> None:
        result = build_site_query("AI news", "example.com")
        assert result == "AI news site:example.com"

    def test_with_subdomain(self) -> None:
        result = build_site_query("test", "news.example.com")
        assert result == "test site:news.example.com"

    def test_empty_query(self) -> None:
        result = build_site_query("", "example.com")
        assert result == " site:example.com"
