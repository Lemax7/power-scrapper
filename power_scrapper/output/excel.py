"""Excel (.xlsx) output writer using pandas + openpyxl."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from power_scrapper.config import ArticleData
from power_scrapper.errors import OutputError
from power_scrapper.output.base import IOutputWriter

logger = logging.getLogger("power_scrapper.output.excel")

_COLUMNS = [
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


class ExcelWriter(IOutputWriter):
    """Write articles to an Excel ``.xlsx`` file."""

    @property
    def extension(self) -> str:
        return ".xlsx"

    def write(self, articles: list[ArticleData], path: Path) -> Path:
        path = self._ensure_extension(path)
        logger.info("Writing %d articles to %s", len(articles), path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            rows = [asdict(a) for a in articles]
            df = pd.DataFrame(rows, columns=_COLUMNS)
            df.to_excel(path, index=False, engine="openpyxl")
        except Exception as exc:
            raise OutputError(f"Failed to write Excel file {path}: {exc}") from exc

        logger.info("Excel output written successfully: %s", path)
        return path

    # ------------------------------------------------------------------

    def _ensure_extension(self, path: Path) -> Path:
        if path.suffix != self.extension:
            return path.with_suffix(self.extension)
        return path
