"""Markdown output writer -- LLM-ready format for OpenClaw integration."""

from __future__ import annotations

import logging
from pathlib import Path

from power_scrapper.config import ArticleData
from power_scrapper.output.base import IOutputWriter

logger = logging.getLogger(__name__)


class MarkdownWriter(IOutputWriter):
    """Write articles as a single Markdown file with structured metadata headers.

    Format per article::

        # {title}

        - **Source:** {source}
        - **URL:** {url}
        - **Date:** {date_iso}
        - **Snippet:** {snippet}

        ---

        {article_text}

    Articles are separated by a horizontal rule.  An optional *max_chars*
    parameter truncates per-article text (useful for token-aware LLM pipelines).
    """

    def __init__(self, *, max_chars: int | None = None) -> None:
        self._max_chars = max_chars

    @property
    def extension(self) -> str:
        return ".md"

    def write(self, articles: list[ArticleData], path: Path) -> Path:
        path = self._ensure_extension(path)
        logger.info("Writing %d articles to %s", len(articles), path)

        path.parent.mkdir(parents=True, exist_ok=True)

        sections: list[str] = []
        for article in articles:
            sections.append(self._format_article(article))

        content = "\n\n---\n\n".join(sections)
        path.write_text(content, encoding="utf-8")

        logger.info("Markdown output written successfully: %s", path)
        return path

    def _format_article(self, article: ArticleData) -> str:
        """Format a single article as markdown with metadata headers."""
        date_str = article.date.isoformat() if article.date else ""
        snippet = article.body or ""

        lines = [
            f"# {article.title}",
            "",
            f"- **Source:** {article.source}",
            f"- **URL:** {article.url}",
            f"- **Date:** {date_str}",
        ]

        if snippet:
            lines.append(f"- **Snippet:** {snippet}")

        lines.append("")
        lines.append("---")
        lines.append("")

        text = article.article_text or ""
        if self._max_chars and len(text) > self._max_chars:
            text = text[: self._max_chars] + "\n\n[truncated]"
        lines.append(text)

        return "\n".join(lines)

    def _ensure_extension(self, path: Path) -> Path:
        if path.suffix != self.extension:
            return path.with_suffix(self.extension)
        return path
