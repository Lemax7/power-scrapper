"""Tests for the Patchright browser-based text extractor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from power_scrapper.extraction.base import ITextExtractor
from power_scrapper.extraction.cascade import CascadeTextExtractor
from power_scrapper.extraction.patchright_ext import PatchrightExtractor

# ---------------------------------------------------------------------------
# Name property
# ---------------------------------------------------------------------------


class TestPatchrightExtractorName:
    def test_name_is_patchright(self) -> None:
        ext = PatchrightExtractor()
        assert ext.name == "patchright"


# ---------------------------------------------------------------------------
# Graceful skip when patchright not installed
# ---------------------------------------------------------------------------


class TestPatchrightImportFallback:
    async def test_returns_empty_if_patchright_not_installed(self) -> None:
        ext = PatchrightExtractor()
        with patch.dict("sys.modules", {"patchright": None}):
            result = await ext.extract("https://example.com")
        assert result == ""

    async def test_returns_empty_if_trafilatura_not_installed(self) -> None:
        ext = PatchrightExtractor()
        with patch.dict("sys.modules", {"trafilatura": None}):
            result = await ext.extract("https://example.com")
        assert result == ""


# ---------------------------------------------------------------------------
# Cascade integration
# ---------------------------------------------------------------------------


class TestCascadeIncludesPatchright:
    def test_patchright_is_last_in_default_extractors(self) -> None:
        cascade = CascadeTextExtractor()
        names = [e.name for e in cascade._extractors]
        assert "patchright" in names
        assert names[-1] == "patchright"

    def test_patchright_after_crawl4ai(self) -> None:
        cascade = CascadeTextExtractor()
        names = [e.name for e in cascade._extractors]
        if "crawl4ai" in names:
            assert names.index("crawl4ai") < names.index("patchright")


class TestPatchrightNotCalledWhenEarlierSucceeds:
    async def test_earlier_extractor_success_skips_patchright(self) -> None:
        class _GoodExtractor(ITextExtractor):
            async def extract(self, url: str, html: str | None = None) -> str:
                return "A" * 100

            @property
            def name(self) -> str:
                return "good"

        patchright_ext = PatchrightExtractor()
        patchright_ext.extract = AsyncMock(return_value="")  # type: ignore[method-assign]

        cascade = CascadeTextExtractor(extractors=[_GoodExtractor(), patchright_ext])
        result = await cascade.extract("https://example.com")

        assert result == "A" * 100
        patchright_ext.extract.assert_not_called()


# ---------------------------------------------------------------------------
# Cascade close propagation
# ---------------------------------------------------------------------------


class TestCascadeClose:
    async def test_close_propagates_to_extractors(self) -> None:
        mock_ext = MagicMock(spec=PatchrightExtractor)
        mock_ext.name = "patchright"
        mock_ext.close = AsyncMock()

        cascade = CascadeTextExtractor(extractors=[mock_ext])
        await cascade.close()

        mock_ext.close.assert_awaited_once()

    async def test_close_skips_extractors_without_close(self) -> None:
        class _SimpleExtractor(ITextExtractor):
            async def extract(self, url: str, html: str | None = None) -> str:
                return ""

            @property
            def name(self) -> str:
                return "simple"

        cascade = CascadeTextExtractor(extractors=[_SimpleExtractor()])
        # Should not raise
        await cascade.close()

    async def test_close_continues_after_error(self) -> None:
        ext1 = MagicMock()
        ext1.name = "broken"
        ext1.close = AsyncMock(side_effect=RuntimeError("boom"))

        ext2 = MagicMock()
        ext2.name = "good"
        ext2.close = AsyncMock()

        cascade = CascadeTextExtractor(extractors=[ext1, ext2])
        await cascade.close()

        ext1.close.assert_awaited_once()
        ext2.close.assert_awaited_once()
