"""HTTP client using NoDriver -- driverless Chrome via CDP.

NoDriver is the successor to undetected-chromedriver.  It uses your real
Chrome installation (not bundled Chromium), communicating directly via
Chrome DevTools Protocol without WebDriver.  Fully async.

Key advantage: uses your real, up-to-date Chrome with real extensions,
fonts, and profiles -- impossible to distinguish from a human browser.
"""

from __future__ import annotations

import logging

from power_scrapper.errors import HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient

logger = logging.getLogger(__name__)


class NoDriverClient(IHttpClient):
    """HTTP client using NoDriver (driverless Chrome via CDP).

    Good for:
    - Initial auth/cookie gathering, then switch to fast HTTP clients
    - Sites that detect bundled Chromium (Patchright) but not real Chrome
    - Extracting session cookies for subsequent httpx/rnet requests

    NoDriver is an optional dependency.
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
        """Lazily start a NoDriver Chrome instance.

        Raises :class:`HttpClientError` if ``nodriver`` is not installed.
        """
        if self._browser is not None:
            return

        try:
            import nodriver as uc  # type: ignore[import-untyped]  # noqa: PLC0415
        except ModuleNotFoundError as exc:
            raise HttpClientError(
                "nodriver is not installed. Install it with: pip install nodriver"
            ) from exc

        try:
            kwargs: dict[str, object] = {"headless": self._headless}
            if self._proxy:
                kwargs["proxy"] = self._proxy
            self._browser = await uc.start(**kwargs)
        except Exception as exc:
            if isinstance(exc, HttpClientError):
                raise
            raise HttpClientError(f"Failed to start NoDriver Chrome: {exc}") from exc

    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Navigate to *url* and return the rendered HTML."""
        await self._ensure_browser()
        try:
            page = await self._browser.get(url)  # type: ignore[union-attr]

            # Wait for the page to settle.
            await page.sleep(2)

            # Get the rendered HTML.
            content = await page.get_content()

            return HttpResponse(
                status_code=200,  # NoDriver doesn't expose status codes directly.
                text=content or "",
                headers={},
                url=url,
            )
        except Exception as exc:
            if isinstance(exc, HttpClientError):
                raise
            raise HttpClientError(f"nodriver GET {url!r} failed: {exc}") from exc

    async def get_cookies(self) -> list[dict[str, object]]:
        """Extract cookies from the browser session.

        Useful for capturing auth cookies to pass to httpx/rnet for
        subsequent fast HTTP requests without browser overhead.
        """
        if self._browser is None:
            return []

        try:
            cookies = await self._browser.cookies.get_all()  # type: ignore[union-attr]
            return [
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path,
                }
                for c in cookies
            ]
        except Exception:  # noqa: BLE001
            logger.debug("Failed to get cookies from NoDriver", exc_info=True)
            return []

    async def close(self) -> None:
        """Stop the NoDriver Chrome instance."""
        if self._browser is not None:
            try:
                self._browser.stop()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                logger.debug("Error stopping NoDriver", exc_info=True)
            self._browser = None

    @property
    def tier_name(self) -> str:  # noqa: D401
        """Client tier identifier."""
        return "nodriver"
