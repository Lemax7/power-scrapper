"""Tests for the GoogleSearchStrategy browser search strategy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from power_scrapper.config import ScraperConfig
from power_scrapper.errors import BotDetectedError
from power_scrapper.search.google_search import (
    BOT_DETECTION_PHRASES,
    GOOGLE_SYSTEM_MESSAGES,
    GoogleSearchStrategy,
    build_google_search_url,
    check_bot_detection,
)

# ---------------------------------------------------------------------------
# Tests: URL building
# ---------------------------------------------------------------------------


class TestBuildGoogleSearchUrl:
    """Test build_google_search_url with different configs."""

    def test_default_config(self) -> None:
        config = ScraperConfig(query="AI news")
        url = build_google_search_url("AI news", config)
        assert "q=AI+news" in url
        assert "hl=ru" in url
        assert "gl=RU" in url
        assert "num=10" in url
        assert url.startswith("https://www.google.com/search?")

    def test_english_config(self) -> None:
        config = ScraperConfig(query="test", language="en", country="US")
        url = build_google_search_url("test", config)
        assert "hl=en" in url
        assert "gl=US" in url

    def test_pagination_offset(self) -> None:
        config = ScraperConfig(query="test")
        url = build_google_search_url("test", config, start=20)
        assert "start=20" in url

    def test_time_period(self) -> None:
        config = ScraperConfig(query="test", time_period="d")
        url = build_google_search_url("test", config)
        assert "tbs=qdr:d" in url

    def test_no_time_period(self) -> None:
        config = ScraperConfig(query="test")
        url = build_google_search_url("test", config)
        assert "tbs=" not in url

    def test_query_encoding(self) -> None:
        config = ScraperConfig(query="test")
        url = build_google_search_url("новости ИИ", config)
        # Cyrillic should be percent-encoded
        assert "q=" in url
        assert " " not in url.split("?")[1]


# ---------------------------------------------------------------------------
# Tests: bot detection
# ---------------------------------------------------------------------------


class TestBotDetection:
    """Test check_bot_detection with known phrases."""

    def test_detects_english_suspicious_traffic(self) -> None:
        assert check_bot_detection("Our systems have detected unusual traffic from your computer")

    def test_detects_russian_suspicious_traffic(self) -> None:
        assert check_bot_detection("Наши системы обнаружили необычный трафик")

    def test_detects_captcha_prompt(self) -> None:
        assert check_bot_detection("Please verify you are human to continue")

    def test_detects_not_a_robot(self) -> None:
        assert check_bot_detection("Confirm that you are not a robot")

    def test_clean_content_not_detected(self) -> None:
        assert not check_bot_detection("<html><body><h1>Search Results</h1></body></html>")

    def test_empty_content(self) -> None:
        assert not check_bot_detection("")

    def test_case_insensitive(self) -> None:
        assert check_bot_detection("SUSPICIOUS TRAFFIC detected")

    @pytest.mark.parametrize("phrase", BOT_DETECTION_PHRASES)
    def test_all_phrases_detected(self, phrase: str) -> None:
        """Every bot detection phrase should trigger detection."""
        assert check_bot_detection(f"<html><body>{phrase}</body></html>")


# ---------------------------------------------------------------------------
# Tests: strategy properties
# ---------------------------------------------------------------------------


class TestGoogleSearchProperties:
    """Test name and is_available."""

    def test_name(self) -> None:
        strategy = GoogleSearchStrategy()
        assert strategy.name == "google_search"

    async def test_is_available_when_patchright_installed(self) -> None:
        strategy = GoogleSearchStrategy()
        # Simulate patchright being importable by injecting a fake module
        fake_module = MagicMock()
        with patch.dict("sys.modules", {"patchright": fake_module}):
            result = await strategy.is_available()
            assert result is True

    async def test_is_available_when_patchright_missing(self) -> None:
        strategy = GoogleSearchStrategy()
        with patch.dict("sys.modules", {"patchright": None}):
            # Patching to None causes ImportError on import
            result = await strategy.is_available()
            assert result is False


# ---------------------------------------------------------------------------
# Tests: search with mocked browser
# ---------------------------------------------------------------------------


def _make_mock_element(
    *,
    href: str = "https://example.com/article",
    title: str = "A Test Article Title That Is Long Enough",
    body: str = "Snippet body text",
    date_text: str = "Jan 15, 2024",
) -> AsyncMock:
    """Create a mock browser element simulating a Google Search result."""
    elem = AsyncMock()

    # Link element
    link_el = AsyncMock()
    link_el.get_attribute = AsyncMock(return_value=href)
    # Title element
    title_el = AsyncMock()
    title_el.inner_text = AsyncMock(return_value=title)
    # Body element
    body_el = AsyncMock()
    body_el.inner_text = AsyncMock(return_value=body)
    # Date element
    date_el = AsyncMock()
    date_el.inner_text = AsyncMock(return_value=date_text)

    async def mock_query_selector(selector: str) -> AsyncMock | None:
        if "a[href]" in selector:
            return link_el
        if "h3" in selector:
            return title_el
        if "data-sncf" in selector or "VwiC3b" in selector:
            return body_el
        if "LEwnzc" in selector or "MUxGbd" in selector:
            return date_el
        return None

    elem.query_selector = mock_query_selector
    return elem


def _make_mock_browser_page(
    *,
    content: str = "<html><body>Search results</body></html>",
    elements: list[AsyncMock] | None = None,
) -> AsyncMock:
    """Create a mock Patchright page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value=content)
    page.close = AsyncMock()

    if elements is None:
        elements = []

    async def mock_query_selector_all(selector: str) -> list[AsyncMock]:
        # Return elements for any of the result selectors
        return elements

    page.query_selector_all = mock_query_selector_all
    return page


def _make_mock_browser(pages: list[AsyncMock]) -> AsyncMock:
    """Create a mock browser that yields pages in order."""
    browser = AsyncMock()
    browser.new_page = AsyncMock(side_effect=pages)
    browser.close = AsyncMock()
    return browser


@patch("power_scrapper.search.google_search.asyncio.sleep", new_callable=AsyncMock)
class TestGoogleSearchIntegration:
    """Test search() with mocked Patchright browser."""

    async def test_search_single_page_with_results(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_element()
        page = _make_mock_browser_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = GoogleSearchStrategy()
        strategy._browser = browser  # Inject mock browser

        config = ScraperConfig(query="AI news")
        articles = await strategy.search("AI news", config, max_pages=1)

        assert len(articles) == 1
        assert articles[0].url == "https://example.com/article"
        assert articles[0].title == "A Test Article Title That Is Long Enough"
        assert articles[0].source_type == "google_search"
        assert articles[0].page == 1
        assert articles[0].position == 1

    async def test_search_skips_short_titles(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_element(title="Short")
        page = _make_mock_browser_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = GoogleSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 0

    async def test_search_skips_google_internal_links(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_element(href="https://www.google.com/settings")
        page = _make_mock_browser_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = GoogleSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 0

    async def test_search_stops_on_empty_results(self, _sleep: AsyncMock) -> None:
        """When a page has no results, pagination should stop."""
        page1 = _make_mock_browser_page(elements=[_make_mock_element()])
        page2 = _make_mock_browser_page(elements=[])  # No results

        browser = _make_mock_browser([page1, page2])

        strategy = GoogleSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=5)

        # Should have stopped after page 2 returned nothing
        assert len(articles) == 1
        assert browser.new_page.call_count == 2

    async def test_search_raises_on_bot_detection(self, _sleep: AsyncMock) -> None:
        page = _make_mock_browser_page(
            content="<html>Our systems have detected unusual traffic</html>"
        )
        browser = _make_mock_browser([page])

        strategy = GoogleSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        with pytest.raises(BotDetectedError, match="Google detected bot activity"):
            await strategy.search("test", config, max_pages=1)

    async def test_search_multi_page(self, _sleep: AsyncMock) -> None:
        elem1 = _make_mock_element(
            href="https://example.com/1", title="First article is long enough"
        )
        elem2 = _make_mock_element(
            href="https://example.com/2", title="Second article is long enough"
        )
        page1 = _make_mock_browser_page(elements=[elem1])
        page2 = _make_mock_browser_page(elements=[elem2])

        browser = _make_mock_browser([page1, page2])

        strategy = GoogleSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=2)

        assert len(articles) == 2
        assert articles[0].page == 1
        assert articles[1].page == 2

    async def test_search_skips_system_messages(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_element(title="People also search for similar topics here")
        page = _make_mock_browser_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = GoogleSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 0

    async def test_close_cleans_up(self, _sleep: AsyncMock) -> None:
        mock_browser = AsyncMock()
        mock_pw = AsyncMock()

        strategy = GoogleSearchStrategy()
        strategy._browser = mock_browser
        strategy._pw = mock_pw

        await strategy.close()

        mock_browser.close.assert_awaited_once()
        mock_pw.stop.assert_awaited_once()
        assert strategy._browser is None
        assert strategy._pw is None

    async def test_close_noop_when_not_started(self, _sleep: AsyncMock) -> None:
        strategy = GoogleSearchStrategy()
        # Should not raise
        await strategy.close()


# ---------------------------------------------------------------------------
# Tests: Google system message filtering
# ---------------------------------------------------------------------------


class TestGoogleSystemMessages:
    """Verify GOOGLE_SYSTEM_MESSAGES list covers expected phrases."""

    @pytest.mark.parametrize("msg", GOOGLE_SYSTEM_MESSAGES)
    def test_system_message_is_lowercase(self, msg: str) -> None:
        """All system messages in the list should be lowercase for matching."""
        assert msg == msg.lower()
