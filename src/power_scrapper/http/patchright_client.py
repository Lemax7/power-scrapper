"""Tier 3 HTTP client: stealth browser via Patchright (Playwright fork)."""

from __future__ import annotations

import logging

from power_scrapper.errors import HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient

logger = logging.getLogger(__name__)


class PatchrightClient(IHttpClient):
    """Tier 3: stealth browser via Patchright (Playwright fork).

    Provides full JavaScript execution and passes bot-detection checks
    that fingerprint-only solutions cannot handle.  Patchright is an
    optional dependency -- if not installed, :meth:`_ensure_browser`
    raises :class:`HttpClientError` on first use.
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
        self._playwright: object | None = None
        self._browser: object | None = None

    async def _ensure_browser(self) -> None:
        """Lazily start Patchright and launch a Chromium instance.

        Raises :class:`HttpClientError` if ``patchright`` is not installed.
        """
        if self._browser is not None:
            return

        try:
            from patchright.async_api import async_playwright  # type: ignore[import-untyped]
        except ModuleNotFoundError as exc:
            raise HttpClientError(
                "patchright is not installed. "
                "Install it with: pip install patchright && patchright install chromium"
            ) from exc

        try:
            self._playwright = await async_playwright().start()
            launch_kwargs: dict[str, object] = {"headless": self._headless}
            if self._proxy:
                launch_kwargs["proxy"] = {"server": self._proxy}
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)  # type: ignore[union-attr]
        except Exception as exc:
            if isinstance(exc, HttpClientError):
                raise
            raise HttpClientError(f"Failed to launch Patchright browser: {exc}") from exc

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
            raise HttpClientError(f"patchright GET {url!r} failed: {exc}") from exc
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:  # noqa: BLE001
                    logger.debug("Error closing patchright page", exc_info=True)

    async def close(self) -> None:
        """Close the browser and stop Patchright."""
        if self._browser is not None:
            try:
                await self._browser.close()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                logger.debug("Error closing patchright browser", exc_info=True)
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                logger.debug("Error stopping patchright", exc_info=True)
            self._playwright = None

    @property
    def tier_name(self) -> str:  # noqa: D401
        """Client tier identifier."""
        return "patchright"
