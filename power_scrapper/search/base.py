"""Abstract base class for search strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from power_scrapper.config import ArticleData, ScraperConfig


class ISearchStrategy(ABC):
    """Interface that every search backend (SearXNG, Google, Yandex, ...) implements."""

    @abstractmethod
    async def search(
        self,
        query: str,
        config: ScraperConfig,
        *,
        max_pages: int = 3,
    ) -> list[ArticleData]:
        """Execute a search and return a list of :class:`ArticleData` results."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Return ``True`` if the backend is reachable and ready."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name (e.g. ``"searxng"``)."""
