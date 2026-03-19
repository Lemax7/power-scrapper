"""Tier 1 HTTP client: async httpx with optional HTTP/2 support."""

from __future__ import annotations

import logging

import httpx

from power_scrapper.config import DEFAULT_USER_AGENT
from power_scrapper.errors import HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient

logger = logging.getLogger(__name__)

# HTTP/2 requires the optional ``h2`` package.  Fall back gracefully.
try:
    import h2 as _h2  # noqa: F401

    _HTTP2_AVAILABLE = True
except ModuleNotFoundError:
    _HTTP2_AVAILABLE = False


class HttpxClient(IHttpClient):
    """Tier 1: async httpx with HTTP/2 support (when ``h2`` is installed)."""

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        user_agent: str | None = None,
        proxy: str | None = None,
    ) -> None:
        ua = user_agent or DEFAULT_USER_AGENT
        self._client = httpx.AsyncClient(
            http2=_HTTP2_AVAILABLE,
            follow_redirects=True,
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": ua},
            proxy=proxy,
        )

    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Make an async GET request and return an :class:`HttpResponse`.

        Raises :class:`HttpClientError` on any transport / HTTP failure.
        """
        try:
            resp = await self._client.get(url, headers=headers)
            return HttpResponse(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                url=str(resp.url),
            )
        except httpx.HTTPError as exc:
            raise HttpClientError(f"httpx GET {url!r} failed: {exc}") from exc

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    @property
    def tier_name(self) -> str:  # noqa: D401
        """Client tier identifier."""
        return "httpx"
