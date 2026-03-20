"""JSON output writer with proper datetime serialisation."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from power_scrapper.config import ArticleData
from power_scrapper.errors import OutputError
from power_scrapper.output.base import IOutputWriter

logger = logging.getLogger("power_scrapper.output.json_writer")


def _json_default(obj: object) -> str:
    """Fallback serialiser for types that :mod:`json` cannot handle natively."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class JsonWriter(IOutputWriter):
    """Write articles to a UTF-8 JSON file (pretty-printed, ASCII-safe for Russian)."""

    @property
    def extension(self) -> str:
        return ".json"

    def write(self, articles: list[ArticleData], path: Path) -> Path:
        path = self._ensure_extension(path)
        logger.info("Writing %d articles to %s", len(articles), path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            data = [asdict(a) for a in articles]
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=_json_default),
                encoding="utf-8",
            )
        except Exception as exc:
            raise OutputError(f"Failed to write JSON file {path}: {exc}") from exc

        logger.info("JSON output written successfully: %s", path)
        return path

    # ------------------------------------------------------------------

    def _ensure_extension(self, path: Path) -> Path:
        if path.suffix != self.extension:
            return path.with_suffix(self.extension)
        return path
