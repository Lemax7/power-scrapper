"""Tests for the cascade text extractor and individual extractor wrappers."""

from __future__ import annotations

from datetime import datetime

from power_scrapper.config import ArticleData
from power_scrapper.extraction.base import ITextExtractor
from power_scrapper.extraction.cascade import CascadeTextExtractor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubExtractor(ITextExtractor):
    """A test-only extractor that returns a configurable result."""

    def __init__(
        self,
        extractor_name: str,
        result: str = "",
        *,
        raise_exc: Exception | None = None,
    ) -> None:
        self._name = extractor_name
        self._result = result
        self._raise_exc = raise_exc
        self.call_count = 0

    async def extract(self, url: str, html: str | None = None) -> str:
        self.call_count += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._result

    @property
    def name(self) -> str:
        return self._name


def _make_article(url: str = "https://example.com/article", article_text: str = "") -> ArticleData:
    return ArticleData(
        url=url,
        title="Test article",
        source="example.com",
        date=datetime(2024, 1, 15),
        article_text=article_text,
    )


# ---------------------------------------------------------------------------
# Cascade: fallthrough behaviour
# ---------------------------------------------------------------------------


class TestCascadeFallthrough:
    """Test that the cascade correctly falls through to the next extractor."""

    async def test_returns_first_successful_result(self) -> None:
        good = _StubExtractor("good", "A" * 100)
        cascade = CascadeTextExtractor(extractors=[good])

        result = await cascade.extract("https://example.com")
        assert result == "A" * 100
        assert good.call_count == 1

    async def test_skips_empty_result(self) -> None:
        empty = _StubExtractor("empty", "")
        good = _StubExtractor("good", "B" * 100)
        cascade = CascadeTextExtractor(extractors=[empty, good])

        result = await cascade.extract("https://example.com")
        assert result == "B" * 100
        assert empty.call_count == 1
        assert good.call_count == 1

    async def test_skips_too_short_result(self) -> None:
        short = _StubExtractor("short", "Too short")
        good = _StubExtractor("good", "C" * 100)
        cascade = CascadeTextExtractor(extractors=[short, good])

        result = await cascade.extract("https://example.com")
        assert result == "C" * 100
        assert short.call_count == 1
        assert good.call_count == 1

    async def test_skips_whitespace_only_result(self) -> None:
        whitespace = _StubExtractor("ws", "   \n\t  ")
        good = _StubExtractor("good", "D" * 100)
        cascade = CascadeTextExtractor(extractors=[whitespace, good])

        result = await cascade.extract("https://example.com")
        assert result == "D" * 100

    async def test_returns_empty_when_all_fail(self) -> None:
        e1 = _StubExtractor("e1", "")
        e2 = _StubExtractor("e2", "short")
        cascade = CascadeTextExtractor(extractors=[e1, e2])

        result = await cascade.extract("https://example.com")
        assert result == ""


# ---------------------------------------------------------------------------
# Cascade: exception handling
# ---------------------------------------------------------------------------


class TestCascadeExceptionHandling:
    """Test that exceptions in one extractor don't break the cascade."""

    async def test_continues_after_exception(self) -> None:
        broken = _StubExtractor("broken", raise_exc=RuntimeError("boom"))
        good = _StubExtractor("good", "E" * 100)
        cascade = CascadeTextExtractor(extractors=[broken, good])

        result = await cascade.extract("https://example.com")
        assert result == "E" * 100
        assert broken.call_count == 1
        assert good.call_count == 1

    async def test_returns_empty_when_all_raise(self) -> None:
        e1 = _StubExtractor("e1", raise_exc=ValueError("v"))
        e2 = _StubExtractor("e2", raise_exc=TypeError("t"))
        cascade = CascadeTextExtractor(extractors=[e1, e2])

        result = await cascade.extract("https://example.com")
        assert result == ""

    async def test_exception_then_short_then_good(self) -> None:
        e1 = _StubExtractor("e1", raise_exc=RuntimeError("err"))
        e2 = _StubExtractor("e2", "short")
        e3 = _StubExtractor("e3", "F" * 100)
        cascade = CascadeTextExtractor(extractors=[e1, e2, e3])

        result = await cascade.extract("https://example.com")
        assert result == "F" * 100
        assert e1.call_count == 1
        assert e2.call_count == 1
        assert e3.call_count == 1


# ---------------------------------------------------------------------------
# Cascade: stops early
# ---------------------------------------------------------------------------


class TestCascadeStopsEarly:
    """The cascade should NOT call subsequent extractors after a success."""

    async def test_does_not_call_later_extractors(self) -> None:
        good = _StubExtractor("good", "G" * 100)
        never = _StubExtractor("never", "H" * 100)
        cascade = CascadeTextExtractor(extractors=[good, never])

        result = await cascade.extract("https://example.com")
        assert result == "G" * 100
        assert good.call_count == 1
        assert never.call_count == 0


# ---------------------------------------------------------------------------
# Cascade: name property
# ---------------------------------------------------------------------------


class TestCascadeName:
    async def test_name_is_cascade(self) -> None:
        cascade = CascadeTextExtractor(extractors=[])
        assert cascade.name == "cascade"


# ---------------------------------------------------------------------------
# Cascade: extract_batch
# ---------------------------------------------------------------------------


class TestExtractBatch:
    """Test batch extraction of multiple articles."""

    async def test_extracts_for_articles_without_text(self) -> None:
        good = _StubExtractor("good", "X" * 100)
        cascade = CascadeTextExtractor(extractors=[good])

        articles = [_make_article(f"https://example.com/{i}") for i in range(3)]
        result = await cascade.extract_batch(articles)

        assert len(result) == 3
        for article in result:
            assert article.article_text == "X" * 100
        assert good.call_count == 3

    async def test_skips_articles_with_existing_text(self) -> None:
        good = _StubExtractor("good", "Y" * 100)
        cascade = CascadeTextExtractor(extractors=[good])

        articles = [
            _make_article("https://example.com/1", article_text="Already extracted"),
            _make_article("https://example.com/2"),
        ]
        result = await cascade.extract_batch(articles)

        assert result[0].article_text == "Already extracted"
        assert result[1].article_text == "Y" * 100
        # Only the second article should trigger extraction
        assert good.call_count == 1

    async def test_batch_with_no_articles(self) -> None:
        good = _StubExtractor("good", "Z" * 100)
        cascade = CascadeTextExtractor(extractors=[good])

        result = await cascade.extract_batch([])
        assert result == []
        assert good.call_count == 0

    async def test_batch_respects_max_concurrent(self) -> None:
        """Ensure batch completes even with concurrency limit of 1."""
        good = _StubExtractor("good", "W" * 100)
        cascade = CascadeTextExtractor(extractors=[good])

        articles = [_make_article(f"https://example.com/{i}") for i in range(5)]
        result = await cascade.extract_batch(articles, max_concurrent=1)

        assert len(result) == 5
        assert all(a.article_text == "W" * 100 for a in result)
        assert good.call_count == 5

    async def test_batch_handles_extraction_failures(self) -> None:
        """Articles where extraction fails should have empty article_text."""
        empty = _StubExtractor("empty", "")
        cascade = CascadeTextExtractor(extractors=[empty])

        articles = [_make_article(f"https://example.com/{i}") for i in range(3)]
        result = await cascade.extract_batch(articles)

        assert len(result) == 3
        for article in result:
            assert article.article_text == ""


# ---------------------------------------------------------------------------
# Cascade: html passthrough
# ---------------------------------------------------------------------------


class TestCascadeHtmlPassthrough:
    """Verify that provided HTML is forwarded to extractors."""

    async def test_html_is_passed_to_extractor(self) -> None:
        captured_html: list[str | None] = []

        class _CapturingExtractor(ITextExtractor):
            async def extract(self, url: str, html: str | None = None) -> str:
                captured_html.append(html)
                return "captured " * 20

            @property
            def name(self) -> str:
                return "capturing"

        cascade = CascadeTextExtractor(extractors=[_CapturingExtractor()])
        await cascade.extract("https://example.com", html="<html>test</html>")
        assert captured_html == ["<html>test</html>"]


# ---------------------------------------------------------------------------
# Individual extractors: graceful import failure
# ---------------------------------------------------------------------------


class TestIndividualExtractorNames:
    """Verify name properties of all concrete extractors."""

    def test_trafilatura_name(self) -> None:
        from power_scrapper.extraction.trafilatura_ext import TrafilaturaExtractor

        assert TrafilaturaExtractor().name == "trafilatura"

    def test_newspaper_name(self) -> None:
        from power_scrapper.extraction.newspaper_ext import NewspaperExtractor

        assert NewspaperExtractor().name == "newspaper4k"

    def test_readability_name(self) -> None:
        from power_scrapper.extraction.readability_ext import ReadabilityExtractor

        assert ReadabilityExtractor().name == "readability"

    def test_crawl4ai_name(self) -> None:
        from power_scrapper.extraction.crawl4ai_ext import Crawl4AIExtractor

        assert Crawl4AIExtractor().name == "crawl4ai"


class TestGracefulImportFailure:
    """When underlying libraries are not installed, extractors return ''."""

    async def test_trafilatura_returns_empty_if_not_installed(self) -> None:
        """trafilatura may or may not be installed -- this just verifies no crash."""
        from power_scrapper.extraction.trafilatura_ext import TrafilaturaExtractor

        ext = TrafilaturaExtractor()
        # Will return "" if trafilatura not installed, or attempt real extraction
        result = await ext.extract("https://httpbin.org/html")
        assert isinstance(result, str)

    async def test_newspaper_returns_empty_if_not_installed(self) -> None:
        from power_scrapper.extraction.newspaper_ext import NewspaperExtractor

        ext = NewspaperExtractor()
        result = await ext.extract("https://httpbin.org/html")
        assert isinstance(result, str)

    async def test_readability_returns_empty_if_not_installed(self) -> None:
        from power_scrapper.extraction.readability_ext import ReadabilityExtractor

        ext = ReadabilityExtractor()
        # Pass html to avoid an HTTP call if readability IS installed
        html = "<html><body><p>Hi</p></body></html>"
        result = await ext.extract("https://example.com", html=html)
        assert isinstance(result, str)

    async def test_crawl4ai_returns_empty_if_not_installed(self) -> None:
        from power_scrapper.extraction.crawl4ai_ext import Crawl4AIExtractor

        ext = Crawl4AIExtractor()
        result = await ext.extract("https://httpbin.org/html")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Default extractors list
# ---------------------------------------------------------------------------


class TestDefaultExtractors:
    def test_default_list_is_not_empty(self) -> None:
        cascade = CascadeTextExtractor()
        assert len(cascade._extractors) >= 1

    def test_trafilatura_is_always_first(self) -> None:
        cascade = CascadeTextExtractor()
        assert cascade._extractors[0].name == "trafilatura"
