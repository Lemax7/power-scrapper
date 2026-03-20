"""HTTP abstractions for power_scrapper."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class HttpResponse:
    """Unified response object returned by all HTTP client implementations."""

    status_code: int
    text: str
    headers: dict[str, str]
    url: str


class IHttpClient(ABC):
    """Abstract base class for async HTTP clients.

    Every concrete tier (httpx, curl_cffi, Playwright) implements this
    interface so the upper layers can swap transports transparently.
    """

    @abstractmethod
    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Perform an async GET request and return an :class:`HttpResponse`."""

    @abstractmethod
    async def close(self) -> None:
        """Release underlying resources (connection pools, etc.)."""

    @property
    @abstractmethod
    def tier_name(self) -> str:
        """Human-readable identifier for this client tier (e.g. ``"httpx"``)."""
