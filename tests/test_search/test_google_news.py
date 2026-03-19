"""Tests for the GoogleNewsStrategy browser search strategy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from power_scrapper.config import ScraperConfig
from power_scrapper.errors import BotDetectedError
from power_scrapper.search.google_news import (
    GoogleNewsStrategy,
    build_google_news_url,
)

# ---------------------------------------------------------------------------
# Tests: URL building
# ---------------------------------------------------------------------------


class TestBuildGoogleNewsUrl:
    """Test build_google_news_url with different configs."""

    def test_default_config(self) -> None:
        config = ScraperConfig(query="AI news")
        url = build_google_news_url("AI news", config)
        assert "q=AI+news" in url
        assert "hl=ru" in url
        assert "gl=RU" in url
        assert "tbm=nws" in url
        assert url.startswith("https://www.google.com/search?")

    def test_english_config(self) -> None:
        config = ScraperConfig(query="test", language="en", country="US")
        url = build_google_news_url("test", config)
        assert "hl=en" in url
        assert "gl=US" in url
        assert "tbm=nws" in url

    def test_pagination(self) -> None:
        config = ScraperConfig(query="test")
        url = build_google_news_url("test", config, start=30)
        assert "start=30" in url

    def test_time_period(self) -> None:
        config = ScraperConfig(query="test", time_period="w")
        url = build_google_news_url("test", config)
        assert "tbs=qdr:w" in url

    def test_no_time_period(self) -> None:
        config = ScraperConfig(query="test")
        url = build_google_news_url("test", config)
        assert "tbs=" not in url


# ---------------------------------------------------------------------------
# Tests: strategy properties
# ---------------------------------------------------------------------------


class TestGoogleNewsProperties:
    """Test name and is_available."""

    def test_name(self) -> None:
        strategy = GoogleNewsStrategy()
        assert strategy.name == "google_news"

    async def test_is_available_when_patchright_installed(self) -> None:
        strategy = GoogleNewsStrategy()
        fake_module = MagicMock()
        with patch.dict("sys.modules", {"patchright": fake_module}):
            result = await strategy.is_available()
            assert result is True

    async def test_is_available_when_patchright_missing(self) -> None:
        strategy = GoogleNewsStrategy()
        with patch.dict("sys.modules", {"patchright": None}):
            result = await strategy.is_available()
            assert result is False


# ---------------------------------------------------------------------------
# Helpers for mocking
# ---------------------------------------------------------------------------


def _make_mock_news_element(
    *,
    href: str = "https://ria.ru/20240115/news.html",
    title: str = "Breaking News About Technology and AI",
    source_text: str = "RIA Novosti",
    date_text: str = "2 hours ago",
    body: str = "",
) -> AsyncMock:
    """Create a mock browser element simulating a Google News result."""
    elem = AsyncMock()

    link_el = AsyncMock()
    link_el.get_attribute = AsyncMock(return_value=href)

    title_el = AsyncMock()
    title_el.inner_text = AsyncMock(return_value=title)

    source_el = AsyncMock()
    source_el.inner_text = AsyncMock(return_value=source_text)

    date_el = AsyncMock()
    date_el.get_attribute = AsyncMock(return_value=None)
    date_el.inner_text = AsyncMock(return_value=date_text)

    body_el = AsyncMock() if body else None
    if body_el:
        body_el.inner_text = AsyncMock(return_value=body)

    async def mock_query_selector(selector: str) -> AsyncMock | None:
        if "a[href]" in selector:
            return link_el
        if "role='heading'" in selector or "h3" in selector:
            return title_el
        if "g-img" in selector or "CEMjEf" in selector:
            return source_el
        if "time" in selector:
            return date_el
        if "GI74Re" in selector:
            return body_el
        return None

    elem.query_selector = mock_query_selector
    return elem


def _make_mock_news_page(
    *,
    content: str = "<html><body>News results</body></html>",
    elements: list[AsyncMock] | None = None,
) -> AsyncMock:
    page = AsyncMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value=content)
    page.close = AsyncMock()

    if elements is None:
        elements = []

    async def mock_query_selector_all(selector: str) -> list[AsyncMock]:
        return elements

    page.query_selector_all = mock_query_selector_all
    return page


def _make_mock_browser(pages: list[AsyncMock]) -> AsyncMock:
    browser = AsyncMock()
    browser.new_page = AsyncMock(side_effect=pages)
    browser.close = AsyncMock()
    return browser


# ---------------------------------------------------------------------------
# Tests: search with mocked browser
# ---------------------------------------------------------------------------


@patch("power_scrapper.search.google_news.asyncio.sleep", new_callable=AsyncMock)
class TestGoogleNewsSearch:
    """Test GoogleNewsStrategy.search() with mocked browser."""

    async def test_single_page_with_results(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_news_element()
        page = _make_mock_news_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = GoogleNewsStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="AI news")
        articles = await strategy.search("AI news", config, max_pages=1)

        assert len(articles) == 1
        assert articles[0].url == "https://ria.ru/20240115/news.html"
        assert articles[0].source_type == "google_news"
        assert articles[0].page == 1
        assert articles[0].position == 1

    async def test_raises_on_bot_detection(self, _sleep: AsyncMock) -> None:
        page = _make_mock_news_page(
            content="<html>Our systems have detected unusual traffic</html>"
        )
        browser = _make_mock_browser([page])

        strategy = GoogleNewsStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        with pytest.raises(BotDetectedError, match="Google News detected bot activity"):
            await strategy.search("test", config, max_pages=1)

    async def test_stops_on_empty_results(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_news_element()
        page1 = _make_mock_news_page(elements=[elem])
        page2 = _make_mock_news_page(elements=[])

        browser = _make_mock_browser([page1, page2])

        strategy = GoogleNewsStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=5)

        assert len(articles) == 1
        assert browser.new_page.call_count == 2

    async def test_skips_short_titles(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_news_element(title="Short")
        page = _make_mock_news_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = GoogleNewsStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 0

    async def test_skips_google_internal_links(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_news_element(href="https://news.google.com/something")
        page = _make_mock_news_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = GoogleNewsStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 0

    async def test_close(self, _sleep: AsyncMock) -> None:
        mock_browser = AsyncMock()
        mock_pw = AsyncMock()

        strategy = GoogleNewsStrategy()
        strategy._browser = mock_browser
        strategy._pw = mock_pw

        await strategy.close()

        mock_browser.close.assert_awaited_once()
        mock_pw.stop.assert_awaited_once()
        assert strategy._browser is None
        assert strategy._pw is None
