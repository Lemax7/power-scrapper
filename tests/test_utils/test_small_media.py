"""Tests for power_scrapper.utils.small_media."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from power_scrapper.utils.small_media import SmallMediaLoader

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def english_excel(tmp_path: Path) -> Path:
    """Create a small Excel file with English column names."""
    df = pd.DataFrame(
        {
            "source": [
                "https://big-news.com/article",
                "https://medium-outlet.ru/post",
                "https://www.small-blog.net/entry",
                "https://tiny-paper.org/story",
                "https://mega-media.com/news",
                "https://local-gazette.ru/report",
                "https://national-daily.com/article",
                "https://micro-digest.net/piece",
            ],
            "name": [
                "Big News",
                "Medium Outlet",
                "Small Blog",
                "Tiny Paper",
                "Mega Media",
                "Local Gazette",
                "National Daily",
                "Micro Digest",
            ],
            "visibility": [
                100.0,
                80.0,
                5.0,
                3.0,
                95.0,
                10.0,
                90.0,
                2.0,
            ],
        }
    )
    path = tmp_path / "media_en.xlsx"
    df.to_excel(path, index=False)
    return path


@pytest.fixture()
def russian_excel(tmp_path: Path) -> Path:
    """Create a small Excel file with Russian column names."""
    df = pd.DataFrame(
        {
            "URL статьи": [
                "https://big-news.com/article",
                "https://medium-outlet.ru/post",
                "https://small-blog.net/entry",
                "https://tiny-paper.org/story",
            ],
            "Название": [
                "Big News",
                "Medium Outlet",
                "Small Blog",
                "Tiny Paper",
            ],
            "Заметность": [
                100.0,
                50.0,
                5.0,
                3.0,
            ],
        }
    )
    path = tmp_path / "media_ru.xlsx"
    df.to_excel(path, index=False)
    return path


@pytest.fixture()
def positional_excel(tmp_path: Path) -> Path:
    """Create an Excel file with non-standard column names (fallback to positions)."""
    df = pd.DataFrame(
        {
            "col_a": [
                "https://site-one.com",
                "https://site-two.com",
                "https://site-three.com",
                "https://site-four.com",
            ],
            "col_b": ["Site One", "Site Two", "Site Three", "Site Four"],
            "col_c": [100.0, 50.0, 5.0, 2.0],
        }
    )
    path = tmp_path / "media_pos.xlsx"
    df.to_excel(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSmallMediaLoaderEnglish:
    def test_loads_domains(self, english_excel: Path) -> None:
        loader = SmallMediaLoader(english_excel)
        domains = loader.load()
        assert isinstance(domains, list)
        assert len(domains) > 0

    def test_filters_to_q1(self, english_excel: Path) -> None:
        """Domains returned should be from low-visibility sources."""
        loader = SmallMediaLoader(english_excel)
        domains = loader.load()
        # The visibilities are [100, 80, 5, 3, 95, 10, 90, 2]
        # Q1 (25th percentile) = ~4.5
        # Below Q1: 3.0, 2.0 -> tiny-paper.org, micro-digest.net
        assert "tiny-paper.org" in domains
        assert "micro-digest.net" in domains
        # High-visibility outlets should NOT appear
        assert "big-news.com" not in domains
        assert "mega-media.com" not in domains

    def test_domains_property_caches(self, english_excel: Path) -> None:
        loader = SmallMediaLoader(english_excel)
        d1 = loader.domains
        d2 = loader.domains
        assert d1 is d2  # same object (cached)

    def test_strips_www_prefix(self, english_excel: Path) -> None:
        loader = SmallMediaLoader(english_excel)
        domains = loader.load()
        # "https://www.small-blog.net/entry" -> "small-blog.net"
        for d in domains:
            assert not d.startswith("www.")


class TestSmallMediaLoaderRussian:
    def test_loads_with_russian_columns(self, russian_excel: Path) -> None:
        loader = SmallMediaLoader(russian_excel)
        domains = loader.load()
        assert isinstance(domains, list)
        assert len(domains) > 0

    def test_filters_to_q1_russian(self, russian_excel: Path) -> None:
        """Russian columns: visibilities [100, 50, 5, 3], Q1 ~ 4.5, below: 3.0 -> tiny-paper.org."""
        loader = SmallMediaLoader(russian_excel)
        domains = loader.load()
        assert "tiny-paper.org" in domains
        assert "big-news.com" not in domains


class TestSmallMediaLoaderPositional:
    def test_falls_back_to_positions(self, positional_excel: Path) -> None:
        loader = SmallMediaLoader(positional_excel)
        domains = loader.load()
        assert isinstance(domains, list)
        # Visibilities [100, 50, 5, 2], Q1 ~ 4.25, below: 2.0 -> site-four.com
        assert "site-four.com" in domains
        assert "site-one.com" not in domains


class TestSmallMediaLoaderEdgeCases:
    def test_nonexistent_file(self, tmp_path: Path) -> None:
        loader = SmallMediaLoader(tmp_path / "nonexistent.xlsx")
        domains = loader.load()
        assert domains == []

    def test_domains_property_with_nonexistent(self, tmp_path: Path) -> None:
        loader = SmallMediaLoader(tmp_path / "nonexistent.xlsx")
        assert loader.domains == []

    def test_empty_excel(self, tmp_path: Path) -> None:
        """An Excel file with columns but no data rows should return empty."""
        df = pd.DataFrame({"source": [], "visibility": []})
        path = tmp_path / "empty.xlsx"
        df.to_excel(path, index=False)
        loader = SmallMediaLoader(path)
        domains = loader.load()
        assert domains == []

    def test_domain_extraction_plain_domain(self) -> None:
        assert SmallMediaLoader._extract_domain("example.com") == "example.com"

    def test_domain_extraction_url(self) -> None:
        assert SmallMediaLoader._extract_domain("https://www.example.com/path") == "example.com"

    def test_domain_extraction_empty(self) -> None:
        assert SmallMediaLoader._extract_domain("") == ""
