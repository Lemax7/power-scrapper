"""Tests for the YandexSearchStrategy browser search strategy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from power_scrapper.config import ScraperConfig
from power_scrapper.errors import BotDetectedError
from power_scrapper.search.yandex import (
    YANDEX_BOT_PHRASES,
    YANDEX_REGIONS,
    YandexSearchStrategy,
    build_yandex_search_url,
    check_yandex_bot_detection,
)

# ---------------------------------------------------------------------------
# Tests: URL building
# ---------------------------------------------------------------------------


class TestBuildYandexSearchUrl:
    """Test build_yandex_search_url with different configs."""

    def test_default_config(self) -> None:
        config = ScraperConfig(query="новости ИИ")
        url = build_yandex_search_url("новости ИИ", config)
        assert "text=" in url
        assert "lr=213" in url  # Moscow for RU
        assert url.startswith("https://yandex.ru/search/?")

    def test_us_region(self) -> None:
        config = ScraperConfig(query="test", country="US")
        url = build_yandex_search_url("test", config)
        assert f"lr={YANDEX_REGIONS['US']}" in url

    def test_pagination(self) -> None:
        config = ScraperConfig(query="test")
        url = build_yandex_search_url("test", config, page_num=3)
        assert "p=3" in url

    def test_unknown_country_defaults_to_moscow(self) -> None:
        config = ScraperConfig(query="test", country="XX")
        url = build_yandex_search_url("test", config)
        assert "lr=213" in url

    def test_query_encoding(self) -> None:
        config = ScraperConfig(query="test")
        url = build_yandex_search_url("AI news", config)
        assert "text=AI+news" in url


# ---------------------------------------------------------------------------
# Tests: bot detection
# ---------------------------------------------------------------------------


class TestYandexBotDetection:
    """Test check_yandex_bot_detection."""

    def test_clean_content(self) -> None:
        assert not check_yandex_bot_detection("<html>Normal search results</html>")

    def test_empty_content(self) -> None:
        assert not check_yandex_bot_detection("")

    def test_russian_captcha_detected(self) -> None:
        assert check_yandex_bot_detection("Подтвердите, что вы не робот, пожалуйста")

    def test_english_captcha_detected(self) -> None:
        assert check_yandex_bot_detection("Please confirm you are not a robot")

    def test_showcaptcha_detected(self) -> None:
        assert check_yandex_bot_detection('<form action="/showcaptcha?cc=1">')

    @pytest.mark.parametrize("phrase", YANDEX_BOT_PHRASES)
    def test_all_phrases_detected(self, phrase: str) -> None:
        assert check_yandex_bot_detection(f"<html>{phrase}</html>")


# ---------------------------------------------------------------------------
# Tests: strategy properties
# ---------------------------------------------------------------------------


class TestYandexProperties:
    """Test name and is_available."""

    def test_name(self) -> None:
        strategy = YandexSearchStrategy()
        assert strategy.name == "yandex"

    async def test_is_available_when_patchright_installed(self) -> None:
        strategy = YandexSearchStrategy()
        fake_module = MagicMock()
        with patch.dict("sys.modules", {"patchright": fake_module}):
            result = await strategy.is_available()
            assert result is True

    async def test_is_available_when_patchright_missing(self) -> None:
        strategy = YandexSearchStrategy()
        with patch.dict("sys.modules", {"patchright": None}):
            result = await strategy.is_available()
            assert result is False


# ---------------------------------------------------------------------------
# Tests: region mapping
# ---------------------------------------------------------------------------


class TestYandexRegions:
    """Test the YANDEX_REGIONS lookup table."""

    def test_russia_is_moscow(self) -> None:
        assert YANDEX_REGIONS["RU"] == 213

    def test_all_regions_are_ints(self) -> None:
        for code, region_id in YANDEX_REGIONS.items():
            assert isinstance(region_id, int), f"{code} has non-int region: {region_id}"

    def test_expected_countries_present(self) -> None:
        expected = {"RU", "UA", "BY", "KZ", "US", "GB"}
        assert expected.issubset(set(YANDEX_REGIONS.keys()))


# ---------------------------------------------------------------------------
# Helpers for mocking
# ---------------------------------------------------------------------------


def _make_mock_yandex_element(
    *,
    href: str = "https://lenta.ru/news/test",
    title: str = "Interesting News Article About AI Technology",
    source_text: str = "lenta.ru",
    body: str = "This is a snippet from the Yandex search result",
    date_text: str = "2 часа назад",
) -> AsyncMock:
    elem = AsyncMock()

    link_el = AsyncMock()
    link_el.get_attribute = AsyncMock(return_value=href)

    title_el = AsyncMock()
    title_el.inner_text = AsyncMock(return_value=title)

    source_el = AsyncMock()
    source_el.inner_text = AsyncMock(return_value=source_text)

    body_el = AsyncMock()
    body_el.inner_text = AsyncMock(return_value=body)

    date_el = AsyncMock()
    date_el.inner_text = AsyncMock(return_value=date_text)

    async def mock_query_selector(selector: str) -> AsyncMock | None:
        if "h2 a[href]" in selector:
            return link_el
        if selector == "h2" or "OrganicTitle-LinkText" in selector:
            return title_el
        if "Path" in selector or "OrganicUrl" in selector:
            return source_el
        if "OrganicText" in selector or "TextContainer" in selector:
            return body_el
        if "subtitle" in selector.lower() or "Subtitle" in selector:
            return date_el
        if "a[href]" in selector:
            return link_el
        return None

    elem.query_selector = mock_query_selector
    return elem


def _make_mock_yandex_page(
    *,
    content: str = "<html><body>Yandex results</body></html>",
    elements: list[AsyncMock] | None = None,
    captcha_present: bool = False,
) -> AsyncMock:
    page = AsyncMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value=content)
    page.close = AsyncMock()

    if elements is None:
        elements = []

    async def mock_query_selector_all(selector: str) -> list[AsyncMock]:
        return elements

    async def mock_query_selector(selector: str) -> AsyncMock | None:
        if captcha_present and "captcha" in selector.lower():
            return AsyncMock()
        return None

    page.query_selector_all = mock_query_selector_all
    page.query_selector = mock_query_selector
    return page


def _make_mock_browser(pages: list[AsyncMock]) -> AsyncMock:
    browser = AsyncMock()
    browser.new_page = AsyncMock(side_effect=pages)
    browser.close = AsyncMock()
    return browser


# ---------------------------------------------------------------------------
# Tests: search with mocked browser
# ---------------------------------------------------------------------------


@patch("power_scrapper.search.yandex.asyncio.sleep", new_callable=AsyncMock)
class TestYandexSearch:
    """Test YandexSearchStrategy.search() with mocked browser."""

    async def test_single_page_with_results(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_yandex_element()
        page = _make_mock_yandex_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = YandexSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 1
        assert articles[0].url == "https://lenta.ru/news/test"
        assert articles[0].source_type == "yandex"
        assert articles[0].page == 1
        assert articles[0].position == 1

    async def test_raises_on_bot_detection_text(self, _sleep: AsyncMock) -> None:
        page = _make_mock_yandex_page(content="<html>Подтвердите, что вы не робот</html>")
        browser = _make_mock_browser([page])

        strategy = YandexSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        with pytest.raises(BotDetectedError, match="Yandex detected bot activity"):
            await strategy.search("test", config, max_pages=1)

    async def test_raises_on_captcha_element(self, _sleep: AsyncMock) -> None:
        page = _make_mock_yandex_page(captcha_present=True)
        browser = _make_mock_browser([page])

        strategy = YandexSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        with pytest.raises(BotDetectedError, match="Yandex CAPTCHA detected"):
            await strategy.search("test", config, max_pages=1)

    async def test_stops_on_empty_results(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_yandex_element()
        page1 = _make_mock_yandex_page(elements=[elem])
        page2 = _make_mock_yandex_page(elements=[])

        browser = _make_mock_browser([page1, page2])

        strategy = YandexSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=5)

        assert len(articles) == 1
        assert browser.new_page.call_count == 2

    async def test_skips_yandex_internal_links(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_yandex_element(href="https://yandex.ru/turbo/some-page")
        page = _make_mock_yandex_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = YandexSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 0

    async def test_skips_short_titles(self, _sleep: AsyncMock) -> None:
        elem = _make_mock_yandex_element(title="Short")
        page = _make_mock_yandex_page(elements=[elem])
        browser = _make_mock_browser([page])

        strategy = YandexSearchStrategy()
        strategy._browser = browser

        config = ScraperConfig(query="test")
        articles = await strategy.search("test", config, max_pages=1)

        assert len(articles) == 0

    async def test_close(self, _sleep: AsyncMock) -> None:
        mock_browser = AsyncMock()
        mock_pw = AsyncMock()

        strategy = YandexSearchStrategy()
        strategy._browser = mock_browser
        strategy._pw = mock_pw

        await strategy.close()

        mock_browser.close.assert_awaited_once()
        mock_pw.stop.assert_awaited_once()
        assert strategy._browser is None
        assert strategy._pw is None
