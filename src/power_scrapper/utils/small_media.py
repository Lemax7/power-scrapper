"""Small media source loader -- identifies low-visibility outlets from an Excel file."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

logger = logging.getLogger(__name__)


class SmallMediaLoader:
    """Load small media sources from Excel file.

    Identifies low-visibility media outlets by filtering the source list
    to those below the first quartile of visibility scores.
    """

    def __init__(self, excel_path: str | Path = "media_sources.xlsx") -> None:
        self._path = Path(excel_path)
        self._domains: list[str] | None = None

    def load(self) -> list[str]:
        """Load and return list of small media domains.

        Reads the Excel file and detects column names using three strategies:

        1. Russian column names: "Заметность" (visibility), "URL статьи" (source)
        2. English column names: "visibility", "source"
        3. Fallback: column positions (0 = source, 2 = visibility)

        Filters to the first quartile (Q1, below 25th percentile) of
        visibility scores, then extracts unique domains.
        """
        if not self._path.exists():
            logger.warning("Small media file not found: %s", self._path)
            self._domains = []
            return self._domains

        df = pd.read_excel(self._path)
        logger.debug("Loaded %d rows from %s (columns: %s)", len(df), self._path, list(df.columns))

        # Detect visibility and source columns
        visibility_col: str | None = None
        source_col: str | None = None

        # Strategy 1: Russian column names
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in ("заметность", "заметность"):
                visibility_col = col
            elif col_lower in ("url статьи", "url статьи", "источник"):
                source_col = col

        # Strategy 2: English column names
        if visibility_col is None or source_col is None:
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if col_lower == "visibility" and visibility_col is None:
                    visibility_col = col
                elif col_lower in ("source", "url") and source_col is None:
                    source_col = col

        # Strategy 3: Fallback to column positions
        if visibility_col is None or source_col is None:
            cols = list(df.columns)
            if len(cols) >= 3:
                source_col = source_col or cols[0]
                visibility_col = visibility_col or cols[2]
            elif len(cols) >= 2:
                source_col = source_col or cols[0]
                visibility_col = visibility_col or cols[1]
            else:
                logger.warning("Not enough columns in %s to detect visibility/source", self._path)
                self._domains = []
                return self._domains

        logger.debug("Using columns: source=%r, visibility=%r", source_col, visibility_col)

        # Convert visibility to numeric, drop NaN
        df[visibility_col] = pd.to_numeric(df[visibility_col], errors="coerce")
        df = df.dropna(subset=[visibility_col, source_col])

        if df.empty:
            logger.warning("No valid rows after cleaning in %s", self._path)
            self._domains = []
            return self._domains

        # Filter to Q1 (below 25th percentile)
        q1 = df[visibility_col].quantile(0.25)
        small_df = df[df[visibility_col] < q1]
        logger.debug(
            "Q1 threshold: %.2f, %d/%d sources below Q1",
            q1,
            len(small_df),
            len(df),
        )

        # Extract unique domains from source URLs
        domains: list[str] = []
        for url_value in small_df[source_col].unique():
            domain = self._extract_domain(str(url_value))
            if domain:
                domains.append(domain)

        self._domains = sorted(set(domains))
        logger.info("Loaded %d small media domains from %s", len(self._domains), self._path)
        return self._domains

    @property
    def domains(self) -> list[str]:
        """Return cached domains, loading from file on first access."""
        if self._domains is None:
            self.load()
        return self._domains or []

    @staticmethod
    def _extract_domain(url_or_domain: str) -> str:
        """Extract domain from a URL or return the string if already a domain."""
        url_or_domain = url_or_domain.strip()
        if not url_or_domain:
            return ""

        # If it looks like a URL, parse it
        if "://" in url_or_domain:
            parsed = urlparse(url_or_domain)
            host = parsed.netloc or parsed.path
        elif "/" in url_or_domain:
            host = url_or_domain.split("/")[0]
        else:
            host = url_or_domain

        # Strip www. prefix and port
        host = host.split(":")[0]
        if host.startswith("www."):
            host = host[4:]

        return host.lower()
