"""Tests for power_scrapper.utils.date_parser."""

from __future__ import annotations

from datetime import datetime, timedelta

from power_scrapper.utils.date_parser import DateParser

# ---------------------------------------------------------------------------
# Russian relative dates
# ---------------------------------------------------------------------------


class TestRussianRelativeDates:
    def test_hours_ago(self) -> None:
        result = DateParser.parse_date("2 часа назад")
        assert abs((datetime.now() - timedelta(hours=2)) - result) < timedelta(seconds=5)

    def test_minutes_ago(self) -> None:
        result = DateParser.parse_date("5 минут назад")
        assert abs((datetime.now() - timedelta(minutes=5)) - result) < timedelta(seconds=5)

    def test_days_ago(self) -> None:
        result = DateParser.parse_date("3 дня назад")
        assert abs((datetime.now() - timedelta(days=3)) - result) < timedelta(seconds=5)

    def test_weeks_ago(self) -> None:
        result = DateParser.parse_date("1 неделю назад")
        assert abs((datetime.now() - timedelta(weeks=1)) - result) < timedelta(seconds=5)

    def test_hour_singular(self) -> None:
        result = DateParser.parse_date("1 час назад")
        assert abs((datetime.now() - timedelta(hours=1)) - result) < timedelta(seconds=5)

    def test_days_plural_dney(self) -> None:
        result = DateParser.parse_date("7 дней назад")
        assert abs((datetime.now() - timedelta(days=7)) - result) < timedelta(seconds=5)


# ---------------------------------------------------------------------------
# English relative dates
# ---------------------------------------------------------------------------


class TestEnglishRelativeDates:
    def test_hours_ago(self) -> None:
        result = DateParser.parse_date("2 hours ago")
        assert abs((datetime.now() - timedelta(hours=2)) - result) < timedelta(seconds=5)

    def test_minutes_ago(self) -> None:
        result = DateParser.parse_date("5 minutes ago")
        assert abs((datetime.now() - timedelta(minutes=5)) - result) < timedelta(seconds=5)

    def test_days_ago(self) -> None:
        result = DateParser.parse_date("3 days ago")
        assert abs((datetime.now() - timedelta(days=3)) - result) < timedelta(seconds=5)

    def test_week_singular(self) -> None:
        result = DateParser.parse_date("1 week ago")
        assert abs((datetime.now() - timedelta(weeks=1)) - result) < timedelta(seconds=5)


# ---------------------------------------------------------------------------
# Absolute dates
# ---------------------------------------------------------------------------


class TestAbsoluteDates:
    def test_month_day_year(self) -> None:
        result = DateParser.parse_date("Jan 15, 2024")
        assert result == datetime(2024, 1, 15)

    def test_iso_format(self) -> None:
        result = DateParser.parse_date("2024-01-15")
        assert result == datetime(2024, 1, 15)

    def test_day_month_year(self) -> None:
        result = DateParser.parse_date("15 Jan 2024")
        assert result == datetime(2024, 1, 15)

    def test_dotted_format(self) -> None:
        result = DateParser.parse_date("15.01.2024")
        assert result == datetime(2024, 1, 15)

    def test_full_month_name(self) -> None:
        result = DateParser.parse_date("January 15, 2024")
        assert result == datetime(2024, 1, 15)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_string_returns_now(self) -> None:
        result = DateParser.parse_date("")
        assert abs(datetime.now() - result) < timedelta(seconds=5)

    def test_whitespace_only_returns_now(self) -> None:
        result = DateParser.parse_date("   ")
        assert abs(datetime.now() - result) < timedelta(seconds=5)

    def test_garbage_input_returns_now(self) -> None:
        result = DateParser.parse_date("not-a-date-at-all xyz")
        assert abs(datetime.now() - result) < timedelta(seconds=5)

    def test_numeric_garbage(self) -> None:
        result = DateParser.parse_date("99999")
        assert abs(datetime.now() - result) < timedelta(seconds=5)

    def test_leading_trailing_whitespace_stripped(self) -> None:
        result = DateParser.parse_date("  2024-01-15  ")
        assert result == datetime(2024, 1, 15)
