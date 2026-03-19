"""Tests for power_scrapper.utils.dedup."""

from __future__ import annotations

from datetime import datetime

from power_scrapper.config import ArticleData
from power_scrapper.utils.dedup import (
    deduplicate_articles,
    normalize_title_for_deduplication,
)

# ---------------------------------------------------------------------------
# normalize_title_for_deduplication
# ---------------------------------------------------------------------------


class TestNormalizeTitle:
    # -- Prefix removal -------------------------------------------------------

    def test_remove_breaking_prefix(self) -> None:
        assert normalize_title_for_deduplication("Breaking: Big event") == "big event"

    def test_remove_update_prefix(self) -> None:
        assert normalize_title_for_deduplication("Update: New info") == "new info"

    def test_remove_latest_prefix(self) -> None:
        assert normalize_title_for_deduplication("Latest: Headlines") == "headlines"

    def test_remove_russian_srochno_prefix(self) -> None:
        assert normalize_title_for_deduplication("Срочно: Важная новость") == "важная новость"

    def test_remove_russian_news_prefix(self) -> None:
        assert normalize_title_for_deduplication("Новости: Обзор дня") == "обзор дня"

    def test_remove_video_prefix(self) -> None:
        assert normalize_title_for_deduplication("Video: Amazing footage") == "amazing footage"

    def test_remove_photo_prefix(self) -> None:
        assert normalize_title_for_deduplication("Фото: Красивый вид") == "красивый вид"

    # -- Suffix removal -------------------------------------------------------

    def test_remove_lenta_suffix(self) -> None:
        assert normalize_title_for_deduplication("Some headline - lenta.ru") == "some headline"

    def test_remove_ria_suffix(self) -> None:
        assert normalize_title_for_deduplication("Some headline - ria.ru") == "some headline"

    def test_remove_tass_suffix(self) -> None:
        assert normalize_title_for_deduplication("Some headline - tass.ru") == "some headline"

    def test_remove_pipe_news_suffix(self) -> None:
        assert normalize_title_for_deduplication("Headline | news") == "headline"

    def test_remove_pipe_novosti_suffix(self) -> None:
        assert normalize_title_for_deduplication("Заголовок | новости") == "заголовок"

    def test_remove_dash_news_suffix(self) -> None:
        assert normalize_title_for_deduplication("Headline - news") == "headline"

    # -- Punctuation and whitespace -------------------------------------------

    def test_punctuation_removed(self) -> None:
        result = normalize_title_for_deduplication("Hello, world! How's it going?")
        assert result == "hello world how s it going"

    def test_whitespace_collapsed(self) -> None:
        result = normalize_title_for_deduplication("  Too   much    space  ")
        assert result == "too much space"

    def test_combined_normalization(self) -> None:
        raw = "Breaking: Big announcement!!!  - lenta.ru"
        assert normalize_title_for_deduplication(raw) == "big announcement"

    # -- No-op cases -----------------------------------------------------------

    def test_plain_title_unchanged_except_case(self) -> None:
        assert normalize_title_for_deduplication("Simple Title") == "simple title"


# ---------------------------------------------------------------------------
# deduplicate_articles
# ---------------------------------------------------------------------------


def _make_article(
    url: str = "https://example.com/article",
    title: str = "Test Article",
    source: str = "example.com",
) -> ArticleData:
    return ArticleData(url=url, title=title, source=source, date=datetime(2024, 1, 15))


class TestDeduplicateArticles:
    def test_no_duplicates(self, sample_articles: list[ArticleData]) -> None:
        result = deduplicate_articles(sample_articles)
        assert len(result) == len(sample_articles)

    def test_exact_duplicate_removed(self) -> None:
        a1 = _make_article(url="https://ex.com/1", title="Same title")
        a2 = _make_article(url="https://ex.com/1", title="Same title")
        assert len(deduplicate_articles([a1, a2])) == 1

    def test_same_title_different_url_deduped(self) -> None:
        a1 = _make_article(url="https://ex.com/1", title="Identical headline")
        a2 = _make_article(url="https://ex.com/2", title="Identical headline")
        result = deduplicate_articles([a1, a2])
        assert len(result) == 1
        assert result[0].url == "https://ex.com/1"  # first wins

    def test_same_url_different_title_deduped(self) -> None:
        a1 = _make_article(url="https://ex.com/same", title="Title A")
        a2 = _make_article(url="https://ex.com/same", title="Title B")
        result = deduplicate_articles([a1, a2])
        assert len(result) == 1
        assert result[0].title == "Title A"

    def test_normalized_title_match(self) -> None:
        """Titles that differ only by prefix/suffix/punctuation are deduplicated."""
        a1 = _make_article(url="https://ex.com/1", title="Breaking: Big news!")
        a2 = _make_article(url="https://ex.com/2", title="big news - lenta.ru")
        result = deduplicate_articles([a1, a2])
        assert len(result) == 1

    def test_url_scheme_insensitive(self) -> None:
        a1 = _make_article(url="http://ex.com/article", title="Title A")
        a2 = _make_article(url="https://ex.com/article", title="Title B")
        result = deduplicate_articles([a1, a2])
        assert len(result) == 1

    def test_url_trailing_slash_insensitive(self) -> None:
        a1 = _make_article(url="https://ex.com/article", title="Title A")
        a2 = _make_article(url="https://ex.com/article/", title="Title B")
        result = deduplicate_articles([a1, a2])
        assert len(result) == 1

    def test_order_preserved(self) -> None:
        a1 = _make_article(url="https://ex.com/1", title="First")
        a2 = _make_article(url="https://ex.com/2", title="Second")
        a3 = _make_article(url="https://ex.com/3", title="Third")
        result = deduplicate_articles([a1, a2, a3])
        assert [a.title for a in result] == ["First", "Second", "Third"]

    def test_empty_list(self) -> None:
        assert deduplicate_articles([]) == []
