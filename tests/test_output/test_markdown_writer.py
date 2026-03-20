"""Tests for the markdown output writer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from power_scrapper.config import ArticleData
from power_scrapper.output.base import IOutputWriter
from power_scrapper.output.markdown_writer import MarkdownWriter


@pytest.fixture()
def articles() -> list[ArticleData]:
    return [
        ArticleData(
            url="https://example.com/article1",
            title="First Article About AI",
            source="example.com",
            date=datetime(2024, 3, 15, 10, 30),
            body="A snippet about AI developments.",
            article_text="Full text of the first article about artificial intelligence.",
            source_type="searxng",
        ),
        ArticleData(
            url="https://news.site/article2",
            title="Second Article About ML",
            source="news.site",
            date=datetime(2024, 3, 14),
            body="ML snippet.",
            article_text="Full text of the second article about machine learning.",
            source_type="google_search",
        ),
    ]


class TestMarkdownWriter:
    def test_implements_interface(self) -> None:
        assert isinstance(MarkdownWriter(), IOutputWriter)

    def test_extension(self) -> None:
        assert MarkdownWriter().extension == ".md"

    def test_write_creates_file(self, tmp_path: Path, articles: list[ArticleData]) -> None:
        writer = MarkdownWriter()
        out = writer.write(articles, tmp_path / "output.md")
        assert out.exists()
        assert out.suffix == ".md"

    def test_adds_extension_if_missing(self, tmp_path: Path, articles: list[ArticleData]) -> None:
        out = MarkdownWriter().write(articles, tmp_path / "output")
        assert out.suffix == ".md"
        assert out.exists()

    def test_creates_parent_dirs(self, tmp_path: Path, articles: list[ArticleData]) -> None:
        out = MarkdownWriter().write(articles, tmp_path / "deep" / "nested" / "output.md")
        assert out.exists()

    def test_contains_article_title(self, tmp_path: Path, articles: list[ArticleData]) -> None:
        out = MarkdownWriter().write(articles, tmp_path / "output.md")
        content = out.read_text(encoding="utf-8")
        assert "# First Article About AI" in content
        assert "# Second Article About ML" in content

    def test_contains_metadata_headers(self, tmp_path: Path, articles: list[ArticleData]) -> None:
        out = MarkdownWriter().write(articles, tmp_path / "output.md")
        content = out.read_text(encoding="utf-8")
        assert "**Source:** example.com" in content
        assert "**URL:** https://example.com/article1" in content
        assert "**Date:** 2024-03-15" in content
        assert "**Snippet:** A snippet about AI developments." in content

    def test_contains_article_text(self, tmp_path: Path, articles: list[ArticleData]) -> None:
        out = MarkdownWriter().write(articles, tmp_path / "output.md")
        content = out.read_text(encoding="utf-8")
        assert "Full text of the first article" in content
        assert "Full text of the second article" in content

    def test_articles_separated_by_hr(self, tmp_path: Path, articles: list[ArticleData]) -> None:
        out = MarkdownWriter().write(articles, tmp_path / "output.md")
        content = out.read_text(encoding="utf-8")
        # Articles are joined with \n\n---\n\n, and each article has
        # its own --- after metadata, so count total separators.
        assert content.count("\n---\n") >= 2

    def test_empty_articles(self, tmp_path: Path) -> None:
        out = MarkdownWriter().write([], tmp_path / "empty.md")
        content = out.read_text(encoding="utf-8")
        assert content == ""

    def test_max_chars_truncation(self, tmp_path: Path) -> None:
        article = ArticleData(
            url="https://example.com/long",
            title="Long Article",
            source="example.com",
            date=datetime(2024, 1, 1),
            body="snippet",
            article_text="x" * 5000,
            source_type="searxng",
        )
        writer = MarkdownWriter(max_chars=100)
        out = writer.write([article], tmp_path / "output.md")
        content = out.read_text(encoding="utf-8")
        assert "[truncated]" in content
        assert "x" * 5000 not in content

    def test_no_truncation_when_under_limit(self, tmp_path: Path) -> None:
        article = ArticleData(
            url="https://example.com/short",
            title="Short Article",
            source="example.com",
            date=datetime(2024, 1, 1),
            body="snippet",
            article_text="short text",
            source_type="searxng",
        )
        writer = MarkdownWriter(max_chars=1000)
        out = writer.write([article], tmp_path / "output.md")
        content = out.read_text(encoding="utf-8")
        assert "[truncated]" not in content
        assert "short text" in content

    def test_russian_text_preserved(self, tmp_path: Path) -> None:
        article = ArticleData(
            url="https://lenta.ru/news/ai/",
            title="Искусственный интеллект в России",
            source="lenta.ru",
            date=datetime(2024, 1, 15),
            body="Тело статьи.",
            article_text="Полный текст статьи на русском.",
            source_type="searxng",
        )
        out = MarkdownWriter().write([article], tmp_path / "output.md")
        content = out.read_text(encoding="utf-8")
        assert "Искусственный интеллект в России" in content
        assert "Полный текст статьи на русском." in content

    def test_no_snippet_when_body_empty(self, tmp_path: Path) -> None:
        article = ArticleData(
            url="https://example.com/no-body",
            title="No Body Article",
            source="example.com",
            date=datetime(2024, 1, 1),
            body="",
            article_text="Some text.",
            source_type="searxng",
        )
        out = MarkdownWriter().write([article], tmp_path / "output.md")
        content = out.read_text(encoding="utf-8")
        assert "**Snippet:**" not in content
