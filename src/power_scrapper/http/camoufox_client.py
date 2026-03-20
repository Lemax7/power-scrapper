"""Tier 2.5 HTTP client: Camoufox anti-detect Firefox browser.

Camoufox is a Firefox-based anti-detect browser that modifies fingerprints
at the C++ implementation layer -- before JavaScript executes.  It scored
best on CreepJS (indistinguishable from a real browser).

Playwright-API compatible, so minimal code changes vs Patchright.
"""

from __future__ import annotations

import logging

from power_scrapper.errors import HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient

logger = logging.getLogger(__name__)


class CamoufoxClient(IHttpClient):
    """HTTP client using Camoufox anti-detect Firefox browser.

    Sits between rnet (Tier 2) and Patchright (Tier 3) in the tiered
    client.  Best for sites with advanced fingerprinting (DataDome, Akamai)
    that rnet's TLS impersonation alone cannot bypass.

    Camoufox is an optional dependency.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout: float = 15.0,
        proxy: str | None = None,
    ) -> None:
        self._headless = headless
        self._timeout = timeout
        self._proxy = proxy
        self._browser: object | None = None

    async def _ensure_browser(self) -> None:
        """Lazily launch a Camoufox browser instance.

        Raises :class:`HttpClientError` if ``camoufox`` is not installed.
        """
        if self._browser is not None:
            return

        try:
            from camoufox.async_api import (
                AsyncCamoufox,  # type: ignore[import-untyped]  # noqa: PLC0415
            )
        except ModuleNotFoundError as exc:
            raise HttpClientError(
                "camoufox is not installed. "
                "Install with: pip install camoufox && camoufox fetch"
            ) from exc

        try:
            kwargs: dict[str, object] = {"headless": self._headless}
            if self._proxy:
                kwargs["proxy"] = {"server": self._proxy}
            # Camoufox auto-calculates geolocation, timezone, locale
            # from proxy's target region when a proxy is provided.
            self._browser = await AsyncCamoufox(**kwargs).__aenter__()
        except Exception as exc:
            if isinstance(exc, HttpClientError):
                raise
            raise HttpClientError(f"Failed to launch Camoufox: {exc}") from exc

    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Navigate to *url* in a new page and return the rendered HTML."""
        await self._ensure_browser()
        page = None
        try:
            page = await self._browser.new_page()  # type: ignore[union-attr]
            if headers:
                await page.set_extra_http_headers(headers)
            response = await page.goto(
                url, timeout=self._timeout * 1000, wait_until="domcontentloaded"
            )
            content = await page.content()
            status = response.status if response else 0
            return HttpResponse(
                status_code=status,
                text=content,
                headers={},
                url=url,
            )
        except Exception as exc:
            if isinstance(exc, HttpClientError):
                raise
            raise HttpClientError(f"camoufox GET {url!r} failed: {exc}") from exc
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:  # noqa: BLE001
                    logger.debug("Error closing camoufox page", exc_info=True)

    async def close(self) -> None:
        """Close the Camoufox browser."""
        if self._browser is not None:
            try:
                await self._browser.__aexit__(None, None, None)  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                logger.debug("Error closing camoufox browser", exc_info=True)
            self._browser = None

    @property
    def tier_name(self) -> str:  # noqa: D401
        """Client tier identifier."""
        return "camoufox"
