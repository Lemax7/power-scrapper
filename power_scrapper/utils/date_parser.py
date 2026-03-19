"""Date parsing with Russian and English relative-date support."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Russian -> English translation table for relative time expressions
# ---------------------------------------------------------------------------

RUSSIAN_PATTERNS: dict[str, str] = {
    # hours
    "час": "hour",
    "часа": "hour",
    "часов": "hour",
    # minutes
    "минута": "minute",
    "минуты": "minute",
    "минут": "minute",
    # days
    "день": "day",
    "дня": "day",
    "дней": "day",
    # weeks
    "неделя": "week",
    "недели": "week",
    "недель": "week",
    "неделю": "week",
    # ago
    "назад": "ago",
}

# Pre-compiled pattern: match any Russian token (longest first to avoid
# partial matches, e.g. "минуты" before "минут").
_RU_TOKEN_RE = re.compile(
    "|".join(re.escape(k) for k in sorted(RUSSIAN_PATTERNS, key=len, reverse=True))
)

# Relative-time regex (works after Russian -> English translation).
_RELATIVE_RE = re.compile(
    r"(\d+)\s+(hour|minute|day|week)s?\s+ago",
    re.IGNORECASE,
)

# Absolute date formats to try, in order.
_ABSOLUTE_FORMATS: list[str] = [
    "%b %d, %Y",  # Jan 15, 2024
    "%d %b %Y",  # 15 Jan 2024
    "%Y-%m-%d",  # 2024-01-15
    "%d.%m.%Y",  # 15.01.2024
    "%Y/%m/%d",  # 2024/01/15
    "%B %d, %Y",  # January 15, 2024
    "%d %B %Y",  # 15 January 2024
]


class DateParser:
    """Parse date strings in various Russian and English formats."""

    RUSSIAN_PATTERNS = RUSSIAN_PATTERNS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Convert a human-readable date string into a :class:`datetime`.

        Supports:
        * Russian relative dates ("2 часа назад", "5 минут назад")
        * English relative dates ("3 days ago", "1 week ago")
        * Common absolute formats (ISO-8601, "Jan 15, 2024", etc.)

        Returns :func:`datetime.now` when the string cannot be parsed.
        """
        if not date_str or not date_str.strip():
            logger.warning("Empty date string, returning current time")
            return datetime.now()

        normalized = date_str.strip()

        # Step 1: translate Russian tokens to English equivalents.
        normalized = _RU_TOKEN_RE.sub(lambda m: RUSSIAN_PATTERNS[m.group(0)], normalized)

        # Step 2: try relative-time parsing.
        result = DateParser._parse_relative_time(normalized)
        if result is not None:
            return result

        # Step 3: try absolute-date parsing.
        result = DateParser._parse_absolute_date(normalized)
        if result is not None:
            return result

        logger.warning("Unable to parse date string %r, returning current time", date_str)
        return datetime.now()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_relative_time(text: str) -> datetime | None:
        match = _RELATIVE_RE.search(text)
        if not match:
            return None

        amount = int(match.group(1))
        unit = match.group(2).lower()

        delta_kwargs: dict[str, int] = {}
        if unit == "hour":
            delta_kwargs["hours"] = amount
        elif unit == "minute":
            delta_kwargs["minutes"] = amount
        elif unit == "day":
            delta_kwargs["days"] = amount
        elif unit == "week":
            delta_kwargs["weeks"] = amount

        return datetime.now() - timedelta(**delta_kwargs)

    @staticmethod
    def _parse_absolute_date(text: str) -> datetime | None:
        for fmt in _ABSOLUTE_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None
