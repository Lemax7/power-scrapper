"""Shared test fixtures."""

from __future__ import annotations

from datetime import datetime

import pytest

from power_scrapper.config import ArticleData


@pytest.fixture()
def sample_articles() -> list[ArticleData]:
    """Return a diverse list of :class:`ArticleData` for testing."""
    return [
        ArticleData(
            url="https://lenta.ru/news/2024/01/15/article1/",
            title="First test article about AI",
            source="lenta.ru",
            date=datetime(2024, 1, 15),
            body="Body of the first article.",
            article_text="Full text of first article.",
            source_type="searxng",
        ),
        ArticleData(
            url="https://ria.ru/20240115/article2.html",
            title="Second test article about ML",
            source="ria.ru",
            date=datetime(2024, 1, 15),
            body="Body of the second article.",
            article_text="Full text of second article.",
            source_type="google_search",
        ),
        ArticleData(
            url="https://tass.ru/news/article3",
            title="Third test article about robotics",
            source="tass.ru",
            date=datetime(2024, 1, 14),
            body="Body of the third article.",
            article_text="Full text of third article.",
            source_type="google_news",
        ),
        ArticleData(
            url="https://rt.com/news/article4",
            title="Breaking: Fourth article about quantum computing",
            source="rt.com",
            date=datetime(2024, 1, 13),
            body="Body of the fourth article.",
            article_text="Full text of fourth article.",
            source_type="yandex",
        ),
    ]


@pytest.fixture()
def now() -> datetime:
    """Return the current time (snapshot) for approximate comparisons."""
    return datetime.now()
