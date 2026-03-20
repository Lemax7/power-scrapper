"""CSV output writer with UTF-8 BOM for Excel compatibility."""

from __future__ import annotations

import csv
import logging
from dataclasses import asdict
from pathlib import Path

from power_scrapper.config import ArticleData
from power_scrapper.errors import OutputError
from power_scrapper.output.base import IOutputWriter

logger = logging.getLogger("power_scrapper.output.csv_writer")

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


class CsvWriter(IOutputWriter):
    """Write articles to a CSV file encoded as UTF-8 with BOM.

    The BOM (Byte Order Mark) ensures that Microsoft Excel opens the file
    with the correct encoding, which is especially important for Russian text.
    """

    @property
    def extension(self) -> str:
        return ".csv"

    def write(self, articles: list[ArticleData], path: Path) -> Path:
        path = self._ensure_extension(path)
        logger.info("Writing %d articles to %s", len(articles), path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=_COLUMNS, extrasaction="ignore")
                writer.writeheader()
                for article in articles:
                    row = asdict(article)
                    # Ensure date is serialised as ISO string.
                    if hasattr(row["date"], "isoformat"):
                        row["date"] = row["date"].isoformat()
                    writer.writerow(row)
        except Exception as exc:
            raise OutputError(f"Failed to write CSV file {path}: {exc}") from exc

        logger.info("CSV output written successfully: %s", path)
        return path

    # ------------------------------------------------------------------

    def _ensure_extension(self, path: Path) -> Path:
        if path.suffix != self.extension:
            return path.with_suffix(self.extension)
        return path
