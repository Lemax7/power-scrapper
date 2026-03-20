"""Abstract base class for output writers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from power_scrapper.config import ArticleData


class IOutputWriter(ABC):
    """Interface that every output writer must implement."""

    @abstractmethod
    def write(self, articles: list[ArticleData], path: Path) -> Path:
        """Write *articles* to *path*.

        Returns
        -------
        Path
            The actual path written to (may differ from *path* if the
            implementation appends an extension).
        """
        ...

    @property
    @abstractmethod
    def extension(self) -> str:
        """File extension including the leading dot (e.g. ``".xlsx"``)."""
        ...
