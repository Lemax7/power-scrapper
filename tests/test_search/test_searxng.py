"""Tests for the SearXNG search strategy."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from power_scrapper.config import ArticleData, ScraperConfig
from power_scrapper.errors import HttpClientError, SearXNGError
from power_scrapper.http.base import HttpResponse, IHttpClient
from power_scrapper.search.searxng import SearXNGStrategy, _extract_domain

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_http_client(responses: list[HttpResponse] | None = None) -> IHttpClient:
    """Create a mock IHttpClient that returns *responses* in order."""
    mock = AsyncMock(spec=IHttpClient)
    mock.tier_name = "mock"
    if responses:
        mock.get.side_effect = responses
    return mock


def _searxng_json(results: list[dict], number_of_results: int = 100) -> str:
    """Build a SearXNG JSON response body."""
    return json.dumps({"query": "test", "results": results, "number_of_results": number_of_results})


SAMPLE_RESULTS_PAGE1 = [
    {
        "url": "https://example.com/article1",
        "title": "First Article",
        "content": "Snippet of the first article.",
        "publishedDate": "2024-01-15T10:30:00Z",
        "engine": "google",
        "category": "news",
    },
    {
        "url": "https://ria.ru/20240115/something.html",
        "title": "Second Article",
        "content": "Snippet of the second article.",
        "publishedDate": "Jan 15, 2024",
        "engine": "bing",
        "category": "news",
    },
]

SAMPLE_RESULTS_PAGE2 = [
    {
        "url": "https://tass.ru/article3",
        "title": "Third Article",
        "content": "Third snippet.",
        "publishedDate": "2024-01-14",
        "engine": "duckduckgo",
        "category": "news",
    },
]


# ---------------------------------------------------------------------------
# Tests: search()
# ---------------------------------------------------------------------------


class TestSearXNGSearch:
    """Test SearXNGStrategy.search()."""

    async def test_single_page(self) -> None:
        http = _make_http_client([HttpResponse(200, _searxng_json(SAMPLE_RESULTS_PAGE1), {}, "")])
        strategy = SearXNGStrategy("http://localhost:8080", http)
        config = ScraperConfig(query="test")

        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 2
        assert all(isinstance(a, ArticleData) for a in articles)

        first = articles[0]
        assert first.url == "https://example.com/article1"
        assert first.title == "First Article"
        assert first.source == "example.com"
        assert first.body == "Snippet of the first article."
        assert first.source_type == "searxng"
        assert first.page == 1
        assert first.position == 1

        second = articles[1]
        assert second.position == 2
        assert second.source == "ria.ru"

    async def test_multi_page(self) -> None:
        http = _make_http_client(
            [
                HttpResponse(200, _searxng_json(SAMPLE_RESULTS_PAGE1), {}, ""),
                HttpResponse(200, _searxng_json(SAMPLE_RESULTS_PAGE2), {}, ""),
            ]
        )
        strategy = SearXNGStrategy("http://localhost:8080/", http)
        config = ScraperConfig(query="test")

        articles = await strategy.search("test", config, max_pages=2)

        assert len(articles) == 3
        assert articles[2].page == 2
        assert articles[2].position == 1
        assert articles[2].title == "Third Article"

    async def test_stops_on_empty_results(self) -> None:
        http = _make_http_client(
            [
                HttpResponse(200, _searxng_json(SAMPLE_RESULTS_PAGE1), {}, ""),
                HttpResponse(200, _searxng_json([]), {}, ""),
            ]
        )
        strategy = SearXNGStrategy("http://localhost:8080", http)
        config = ScraperConfig(query="test")

        articles = await strategy.search("test", config, max_pages=5)

        # Should have stopped after page 2 returned nothing.
        assert len(articles) == 2
        assert http.get.call_count == 2

    async def test_uses_config_language(self) -> None:
        http = _make_http_client([HttpResponse(200, _searxng_json([]), {}, "")])
        strategy = SearXNGStrategy("http://localhost:8080", http)
        config = ScraperConfig(query="AI news", language="en")

        await strategy.search("AI news", config, max_pages=1)

        called_url = http.get.call_args_list[0][0][0]
        assert "language=en" in called_url
        assert "q=AI+news" in called_url

    async def test_date_parsing(self) -> None:
        results = [
            {
                "url": "https://example.com/a",
                "title": "T",
                "content": "C",
                "publishedDate": "2024-01-15",
                "engine": "google",
            }
        ]
        http = _make_http_client([HttpResponse(200, _searxng_json(results), {}, "")])
        strategy = SearXNGStrategy("http://localhost:8080", http)
        config = ScraperConfig(query="test")

        articles = await strategy.search("test", config, max_pages=1)
        assert articles[0].date == datetime(2024, 1, 15)

    async def test_trailing_slash_stripped(self) -> None:
        http = _make_http_client([HttpResponse(200, _searxng_json([]), {}, "")])
        strategy = SearXNGStrategy("http://localhost:8080///", http)
        config = ScraperConfig(query="test")

        await strategy.search("test", config, max_pages=1)

        called_url = http.get.call_args_list[0][0][0]
        assert called_url.startswith("http://localhost:8080/search")


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestSearXNGErrors:
    """Test error paths."""

    async def test_http_error_raises_searxng_error(self) -> None:
        http = _make_http_client()
        http.get.side_effect = HttpClientError("connection refused")
        strategy = SearXNGStrategy("http://localhost:8080", http)
        config = ScraperConfig(query="test")

        with pytest.raises(SearXNGError, match="HTTP request to SearXNG failed"):
            await strategy.search("test", config, max_pages=1)

    async def test_non_200_raises_searxng_error(self) -> None:
        http = _make_http_client([HttpResponse(502, "Bad Gateway", {}, "")])
        strategy = SearXNGStrategy("http://localhost:8080", http)
        config = ScraperConfig(query="test")

        with pytest.raises(SearXNGError, match="HTTP 502"):
            await strategy.search("test", config, max_pages=1)

    async def test_invalid_json_raises_searxng_error(self) -> None:
        http = _make_http_client([HttpResponse(200, "not json at all", {}, "")])
        strategy = SearXNGStrategy("http://localhost:8080", http)
        config = ScraperConfig(query="test")

        with pytest.raises(SearXNGError, match="invalid JSON"):
            await strategy.search("test", config, max_pages=1)


# ---------------------------------------------------------------------------
# Tests: is_available()
# ---------------------------------------------------------------------------


class TestSearXNGAvailability:
    """Test is_available()."""

    async def test_available_when_200(self) -> None:
        http = _make_http_client([HttpResponse(200, _searxng_json([]), {}, "")])
        strategy = SearXNGStrategy("http://localhost:8080", http)

        assert await strategy.is_available() is True

    async def test_unavailable_on_non_200(self) -> None:
        http = _make_http_client([HttpResponse(500, "error", {}, "")])
        strategy = SearXNGStrategy("http://localhost:8080", http)

        assert await strategy.is_available() is False

    async def test_unavailable_on_connection_error(self) -> None:
        http = _make_http_client()
        http.get.side_effect = HttpClientError("connection refused")
        strategy = SearXNGStrategy("http://localhost:8080", http)

        assert await strategy.is_available() is False


# ---------------------------------------------------------------------------
# Tests: _extract_domain()
# ---------------------------------------------------------------------------


class TestExtractDomain:
    """Test the helper that extracts and decodes domains."""

    def test_simple_url(self) -> None:
        assert _extract_domain("https://example.com/path") == "example.com"

    def test_url_with_port(self) -> None:
        assert _extract_domain("http://localhost:8080/search") == "localhost"

    def test_punycode_domain(self) -> None:
        result = _extract_domain("https://xn--e1afmapc.xn--p1ai/news")
        # Should be decoded to the Unicode representation.
        assert "xn--" not in result

    def test_empty_url(self) -> None:
        assert _extract_domain("") == ""

    def test_url_with_subdomain(self) -> None:
        assert _extract_domain("https://news.ria.ru/article") == "news.ria.ru"


# ---------------------------------------------------------------------------
# Tests: strategy properties
# ---------------------------------------------------------------------------


class TestSearXNGProperties:
    """Test name and other properties."""

    def test_name(self) -> None:
        http = _make_http_client()
        strategy = SearXNGStrategy("http://localhost:8080", http)
        assert strategy.name == "searxng"
