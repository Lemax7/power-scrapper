"""Tier 2 HTTP client: curl_cffi with TLS fingerprint impersonation."""

from __future__ import annotations

import logging

from power_scrapper.errors import HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient

logger = logging.getLogger(__name__)


class CurlCffiClient(IHttpClient):
    """Tier 2: curl_cffi with TLS fingerprint impersonation.

    Bypasses Cloudflare and similar protections by impersonating a real
    browser's TLS handshake.  The ``curl_cffi`` package is an optional
    dependency -- if it is not installed, :meth:`_get_session` raises
    :class:`HttpClientError` on first use.
    """

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        impersonate: str = "chrome124",
        proxy: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._impersonate = impersonate
        self._proxy = proxy
        self._session: object | None = None  # Lazy init

    def _get_session(self) -> object:
        """Return (and lazily create) an async ``curl_cffi`` session.

        Raises :class:`HttpClientError` if the package is not installed.
        """
        if self._session is not None:
            return self._session

        try:
            from curl_cffi.requests import AsyncSession  # type: ignore[import-untyped]
        except ModuleNotFoundError as exc:
            raise HttpClientError(
                "curl_cffi is not installed. "
                "Install it with: pip install curl_cffi"
            ) from exc

        kwargs: dict[str, object] = {
            "impersonate": self._impersonate,
            "timeout": self._timeout,
        }
        if self._proxy:
            kwargs["proxies"] = {"http": self._proxy, "https": self._proxy}

        self._session = AsyncSession(**kwargs)
        return self._session

    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Perform an async GET via curl_cffi and return an :class:`HttpResponse`."""
        session = self._get_session()
        try:
            resp = await session.get(url, headers=headers or {})  # type: ignore[union-attr]
            return HttpResponse(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers) if resp.headers else {},
                url=str(resp.url),
            )
        except Exception as exc:
            if isinstance(exc, HttpClientError):
                raise
            raise HttpClientError(
                f"curl_cffi GET {url!r} failed: {exc}"
            ) from exc

    async def close(self) -> None:
        """Close the underlying curl_cffi session if open."""
        if self._session is not None:
            try:
                await self._session.close()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                logger.debug("Error closing curl_cffi session", exc_info=True)
            self._session = None

    @property
    def tier_name(self) -> str:  # noqa: D401
        """Client tier identifier."""
        return "curl_cffi"
