"""Tests for output writers (Excel, JSON, CSV)."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from power_scrapper.config import ArticleData
from power_scrapper.errors import OutputError
from power_scrapper.output import CsvWriter, ExcelWriter, IOutputWriter, JsonWriter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def russian_articles() -> list[ArticleData]:
    """Articles with Russian text to validate encoding."""
    return [
        ArticleData(
            url="https://lenta.ru/news/2024/01/15/ai/",
            title="Искусственный интеллект в России",
            source="lenta.ru",
            date=datetime(2024, 1, 15, 10, 30, 0),
            body="Тело статьи на русском языке.",
            article_text="Полный текст статьи.",
            source_type="searxng",
            page=1,
            position=1,
            overall_position=1,
        ),
        ArticleData(
            url="https://ria.ru/20240115/ml.html",
            title="Машинное обучение",
            source="ria.ru",
            date=datetime(2024, 1, 15, 12, 0, 0),
            body="Краткое описание.",
            article_text="Развёрнутый текст.",
            source_type="google_search",
            page=1,
            position=2,
            overall_position=2,
        ),
    ]


EXPECTED_COLUMNS = [
    "url",
    "title",
    "source",
    "date",
    "body",
    "article_text",
    "source_type",
    "page",
    "position",
    "overall_position",
]


# ---------------------------------------------------------------------------
# ExcelWriter
# ---------------------------------------------------------------------------


class TestExcelWriter:
    def test_implements_interface(self) -> None:
        assert isinstance(ExcelWriter(), IOutputWriter)

    def test_extension(self) -> None:
        assert ExcelWriter().extension == ".xlsx"

    def test_write_creates_file(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        writer = ExcelWriter()
        out = writer.write(sample_articles, tmp_path / "output.xlsx")
        assert out.exists()
        assert out.suffix == ".xlsx"

    def test_write_correct_columns(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = ExcelWriter().write(sample_articles, tmp_path / "output.xlsx")
        df = pd.read_excel(out, engine="openpyxl")
        assert list(df.columns) == EXPECTED_COLUMNS

    def test_write_correct_row_count(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = ExcelWriter().write(sample_articles, tmp_path / "output.xlsx")
        df = pd.read_excel(out, engine="openpyxl")
        assert len(df) == len(sample_articles)

    def test_write_russian_text(
        self, tmp_path: Path, russian_articles: list[ArticleData]
    ) -> None:
        out = ExcelWriter().write(russian_articles, tmp_path / "output.xlsx")
        df = pd.read_excel(out, engine="openpyxl")
        assert df.iloc[0]["title"] == "Искусственный интеллект в России"

    def test_adds_extension_if_missing(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = ExcelWriter().write(sample_articles, tmp_path / "output")
        assert out.suffix == ".xlsx"
        assert out.exists()

    def test_creates_parent_dirs(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = ExcelWriter().write(
            sample_articles, tmp_path / "deep" / "nested" / "output.xlsx"
        )
        assert out.exists()

    def test_empty_articles(self, tmp_path: Path) -> None:
        out = ExcelWriter().write([], tmp_path / "empty.xlsx")
        df = pd.read_excel(out, engine="openpyxl")
        assert len(df) == 0
        assert list(df.columns) == EXPECTED_COLUMNS


# ---------------------------------------------------------------------------
# JsonWriter
# ---------------------------------------------------------------------------


class TestJsonWriter:
    def test_implements_interface(self) -> None:
        assert isinstance(JsonWriter(), IOutputWriter)

    def test_extension(self) -> None:
        assert JsonWriter().extension == ".json"

    def test_write_creates_valid_json(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = JsonWriter().write(sample_articles, tmp_path / "output.json")
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == len(sample_articles)

    def test_datetime_serialisation(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = JsonWriter().write(sample_articles, tmp_path / "output.json")
        data = json.loads(out.read_text(encoding="utf-8"))
        # Every date should be parseable as ISO format.
        for item in data:
            datetime.fromisoformat(item["date"])

    def test_russian_text_preserved(
        self, tmp_path: Path, russian_articles: list[ArticleData]
    ) -> None:
        out = JsonWriter().write(russian_articles, tmp_path / "output.json")
        raw = out.read_text(encoding="utf-8")
        # ensure_ascii=False means Cyrillic appears literally.
        assert "Искусственный" in raw
        data = json.loads(raw)
        assert data[0]["title"] == "Искусственный интеллект в России"

    def test_adds_extension_if_missing(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = JsonWriter().write(sample_articles, tmp_path / "output")
        assert out.suffix == ".json"

    def test_all_fields_present(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = JsonWriter().write(sample_articles, tmp_path / "output.json")
        data = json.loads(out.read_text(encoding="utf-8"))
        for item in data:
            for col in EXPECTED_COLUMNS:
                assert col in item, f"Missing field: {col}"

    def test_empty_articles(self, tmp_path: Path) -> None:
        out = JsonWriter().write([], tmp_path / "empty.json")
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == []


# ---------------------------------------------------------------------------
# CsvWriter
# ---------------------------------------------------------------------------


class TestCsvWriter:
    def test_implements_interface(self) -> None:
        assert isinstance(CsvWriter(), IOutputWriter)

    def test_extension(self) -> None:
        assert CsvWriter().extension == ".csv"

    def test_write_creates_file(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = CsvWriter().write(sample_articles, tmp_path / "output.csv")
        assert out.exists()
        assert out.suffix == ".csv"

    def test_bom_present(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = CsvWriter().write(sample_articles, tmp_path / "output.csv")
        raw = out.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf", "UTF-8 BOM must be present"

    def test_correct_columns(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = CsvWriter().write(sample_articles, tmp_path / "output.csv")
        with out.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            assert reader.fieldnames == EXPECTED_COLUMNS

    def test_correct_row_count(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = CsvWriter().write(sample_articles, tmp_path / "output.csv")
        with out.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == len(sample_articles)

    def test_russian_text_preserved(
        self, tmp_path: Path, russian_articles: list[ArticleData]
    ) -> None:
        out = CsvWriter().write(russian_articles, tmp_path / "output.csv")
        with out.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert rows[0]["title"] == "Искусственный интеллект в России"

    def test_date_iso_format(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = CsvWriter().write(sample_articles, tmp_path / "output.csv")
        with out.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                # Should be parseable as ISO datetime.
                datetime.fromisoformat(row["date"])

    def test_adds_extension_if_missing(
        self, tmp_path: Path, sample_articles: list[ArticleData]
    ) -> None:
        out = CsvWriter().write(sample_articles, tmp_path / "output")
        assert out.suffix == ".csv"

    def test_empty_articles(self, tmp_path: Path) -> None:
        out = CsvWriter().write([], tmp_path / "empty.csv")
        with out.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == 0
        assert reader.fieldnames == EXPECTED_COLUMNS
