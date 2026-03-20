"""Text cleaning utilities for article snippets and descriptions."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Date prefix patterns to strip from article snippets/descriptions.
# Google and Yandex often prepend dates like "15 янв. 2024 г. — " or
# "3 hours ago — " to the snippet text.
# ---------------------------------------------------------------------------

_DATE_PREFIX_PATTERNS: list[str] = [
    # Russian short months: "15 янв. 2024 г. —"
    r"^\d{1,2}\s+(янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)\.?\s+\d{4}\s+г\.?\s*[—\-]\s*",
    # Russian full months: "15 января 2024 г. —"
    r"^\d{1,2}\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\s+г\.?\s*[—\-]\s*",
    # English short months: "15 Jan 2024 —"
    r"^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{4}\s*[—\-]\s*",
    # Russian relative time: "5 часов назад —"
    r"^\d+\s+(час|часа|часов|минут|минуты|минута|день|дня|дней|неделю|недели|недель|месяц|месяца|месяцев)\s+назад\s*[—\-]\s*",
    # English relative time: "3 hours ago —"
    r"^\d+\s+(hour|hours|minute|minutes|day|days|week|weeks|month|months)\s+ago\s*[—\-]\s*",
]

_COMPILED_DATE_PREFIXES = [re.compile(p, re.IGNORECASE) for p in _DATE_PREFIX_PATTERNS]


def clean_snippet(text: str) -> str:
    """Clean a search result snippet by removing date prefixes and normalizing whitespace.

    Google/Yandex often prepend dates to snippets like:
    - "15 янв. 2024 г. — Actual snippet text"
    - "3 hours ago — Actual snippet text"

    This function strips such prefixes and cleans up leading punctuation.
    """
    if not text:
        return text

    cleaned = text
    for pattern in _COMPILED_DATE_PREFIXES:
        new = pattern.sub("", cleaned)
        if new != cleaned:
            cleaned = new
            break

    # Strip leading dashes, em-dashes, dots, commas, semicolons, colons.
    cleaned = re.sub(r"^[\-\—\.\,\;\:\s]+", "", cleaned)
    # Collapse whitespace.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned
