"""Abstract base class for text extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ITextExtractor(ABC):
    """Interface for article text extraction."""

    @abstractmethod
    async def extract(self, url: str, html: str | None = None) -> str:
        """Extract article text from *url* or provided *html*.

        Returns the extracted text, or an empty string on failure.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable extractor name (used in logging)."""
        ...
