"""Tests for power_scrapper.config."""

from __future__ import annotations

from datetime import datetime

from power_scrapper.config import ArticleData, ScraperConfig


class TestScraperConfig:
    def test_default_values(self) -> None:
        cfg = ScraperConfig(query="test query")
        assert cfg.query == "test query"
        assert cfg.max_pages == 3
        assert cfg.language == "ru"
        assert cfg.country == "RU"
        assert cfg.debug is False
        assert cfg.searxng_url is None
        assert cfg.output_dir == "./output"
        assert cfg.output_formats == ["excel", "json", "csv"]
        assert cfg.use_proxy is False
        assert cfg.proxy_rotation is True
        assert cfg.extract_articles is True
        assert cfg.expand_with_titles is False
        assert cfg.max_titles_to_expand == 5
        assert cfg.time_period is None
        assert cfg.max_concurrent_extractions == 10

    def test_custom_values(self) -> None:
        cfg = ScraperConfig(
            query="AI news",
            max_pages=5,
            language="en",
            country="US",
            debug=True,
            searxng_url="http://localhost:8080",
            use_proxy=True,
        )
        assert cfg.query == "AI news"
        assert cfg.max_pages == 5
        assert cfg.language == "en"
        assert cfg.country == "US"
        assert cfg.debug is True
        assert cfg.searxng_url == "http://localhost:8080"
        assert cfg.use_proxy is True


class TestArticleData:
    def test_required_fields(self) -> None:
        now = datetime.now()
        article = ArticleData(
            url="https://example.com/article",
            title="Test Article",
            source="example.com",
            date=now,
        )
        assert article.url == "https://example.com/article"
        assert article.title == "Test Article"
        assert article.source == "example.com"
        assert article.date == now

    def test_default_optional_fields(self) -> None:
        article = ArticleData(
            url="https://example.com",
            title="Title",
            source="example.com",
            date=datetime(2024, 1, 15),
        )
        assert article.body == ""
        assert article.page == 1
        assert article.position == 0
        assert article.overall_position == 0
        assert article.article_text == ""
        assert article.source_type == "searxng"

    def test_custom_optional_fields(self) -> None:
        article = ArticleData(
            url="https://example.com",
            title="Title",
            source="example.com",
            date=datetime(2024, 1, 15),
            body="Article body text",
            page=2,
            position=3,
            overall_position=13,
            article_text="Full extracted article text.",
            source_type="google_news",
        )
        assert article.body == "Article body text"
        assert article.page == 2
        assert article.position == 3
        assert article.overall_position == 13
        assert article.article_text == "Full extracted article text."
        assert article.source_type == "google_news"
