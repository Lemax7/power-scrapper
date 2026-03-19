"""Article deduplication utilities."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from power_scrapper.config import ArticleData

# ---------------------------------------------------------------------------
# Prefixes & suffixes to strip when normalizing titles
# ---------------------------------------------------------------------------

_TITLE_PREFIXES: list[str] = [
    "breaking:",
    "update:",
    "latest:",
    # Russian
    "срочно:",
    "обновление:",
    "новости:",
    # Mixed / English
    "news:",
    "видео:",
    "video:",
    "фото:",
    "photo:",
]

_TITLE_SUFFIXES: list[str] = [
    "- lenta.ru",
    "- ria.ru",
    "- tass.ru",
    "- rt.com",
    "| новости",
    "| news",
    "- новости",
    "- news",
]


def normalize_title_for_deduplication(title: str) -> str:
    """Normalize a title for duplicate detection.

    Steps:
    1. Lowercase + strip.
    2. Remove known editorial prefixes (e.g. "Breaking:", "Срочно:").
    3. Remove known outlet suffixes (e.g. "- Lenta.ru", "| News").
    4. Strip punctuation (keep word characters and whitespace).
    5. Collapse consecutive whitespace.
    """
    normalized = title.lower().strip()

    # Remove prefixes.
    for prefix in _TITLE_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()

    # Remove suffixes.
    for suffix in _TITLE_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()

    # Remove punctuation, collapse whitespace.
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def _normalize_url(url: str) -> str:
    """Produce a canonical URL key for dedup (scheme-agnostic, no trailing slash)."""
    parsed = urlparse(url)
    # Drop scheme, lowercase host, strip trailing slash from path.
    host = (parsed.netloc or "").lower()
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def deduplicate_articles(articles: list[ArticleData]) -> list[ArticleData]:
    """Remove duplicate articles in a single pass.

    An article is considered a duplicate if it matches a previously seen
    article on **either** of these criteria:
    * Normalized title (see :func:`normalize_title_for_deduplication`).
    * Normalized URL (scheme-insensitive, no trailing slash).

    Original order is preserved; the first occurrence wins.
    """
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    unique: list[ArticleData] = []

    for article in articles:
        norm_title = normalize_title_for_deduplication(article.title)
        norm_url = _normalize_url(article.url)

        if norm_title in seen_titles or norm_url in seen_urls:
            continue

        seen_titles.add(norm_title)
        seen_urls.add(norm_url)
        unique.append(article)

    return unique
