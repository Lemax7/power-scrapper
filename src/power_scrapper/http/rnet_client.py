"""Tier 2 HTTP client: rnet with accurate TLS fingerprint impersonation.

rnet is a Rust-powered Python HTTP client that accurately emulates
Chrome 136, Firefox 139, Safari, and Opera with precise TLS/HTTP2
signatures.  It replaces curl_cffi as the TLS fingerprinting tier.
"""

from __future__ import annotations

import logging

from power_scrapper.errors import HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient

logger = logging.getLogger(__name__)


class RnetClient(IHttpClient):
    """Tier 2: rnet with TLS fingerprint impersonation.

    Bypasses Cloudflare and similar protections by accurately mimicking
    a real browser's TLS handshake using Rust-level precision.

    The ``rnet`` package is an optional dependency -- if not installed,
    :meth:`_get_client` raises :class:`HttpClientError` on first use.
    """

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        impersonate: str = "chrome_136",
        proxy: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._impersonate = impersonate
        self._proxy = proxy
        self._client: object | None = None  # Lazy init

    def _get_client(self) -> object:
        """Return (and lazily create) an rnet client.

        Raises :class:`HttpClientError` if the package is not installed.
        """
        if self._client is not None:
            return self._client

        try:
            import rnet  # type: ignore[import-untyped]  # noqa: PLC0415
        except ModuleNotFoundError as exc:
            raise HttpClientError(
                "rnet is not installed. Install it with: pip install rnet"
            ) from exc

        kwargs: dict[str, object] = {
            "impersonate": self._impersonate,
            "timeout": self._timeout,
        }
        if self._proxy:
            kwargs["proxy"] = self._proxy

        self._client = rnet.Client(**kwargs)
        return self._client

    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Perform an async GET via rnet and return an :class:`HttpResponse`."""
        client = self._get_client()
        try:
            resp = await client.get(url, headers=headers or {})  # type: ignore[union-attr]
            return HttpResponse(
                status_code=resp.status_code,
                text=await resp.text(),  # type: ignore[union-attr]
                headers=dict(resp.headers) if resp.headers else {},
                url=str(resp.url),
            )
        except Exception as exc:
            if isinstance(exc, HttpClientError):
                raise
            raise HttpClientError(f"rnet GET {url!r} failed: {exc}") from exc

    async def close(self) -> None:
        """Close the underlying rnet client."""
        # rnet clients don't require explicit closing, but reset for re-init.
        self._client = None

    @property
    def tier_name(self) -> str:  # noqa: D401
        """Client tier identifier."""
        return "rnet"
