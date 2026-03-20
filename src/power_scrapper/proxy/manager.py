"""Proxy manager: rotation, testing, and state tracking."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from power_scrapper.proxy.base import IProxyProvider, ProxyInfo
from power_scrapper.proxy.sources import (
    GeoNodeProvider,
    GitHubListProvider,
    ProxyScrapeProvider,
)

logger = logging.getLogger(__name__)

_MAX_FAIL_COUNT = 3
_TEST_TIMEOUT = 10.0


class ProxyManager:
    """Manages proxy rotation, testing, and state.

    Parameters
    ----------
    providers:
        Proxy source providers.  Defaults to GeoNode, ProxyScrape, and
        the GitHub list.
    test_url:
        URL used by :meth:`test_proxy` to verify a proxy works.
    """

    def __init__(
        self,
        providers: list[IProxyProvider] | None = None,
        *,
        test_url: str = "https://httpbin.org/ip",
    ) -> None:
        self._providers: list[IProxyProvider] = providers or [
            GeoNodeProvider(),
            ProxyScrapeProvider(),
            GitHubListProvider(),
        ]
        self._test_url = test_url
        self._proxies: list[ProxyInfo] = []
        self._current_index: int = 0

    # -- Fetching ------------------------------------------------------------

    async def fetch_all(self) -> int:
        """Fetch proxies from all providers.  Returns total unique count."""
        all_proxies: list[ProxyInfo] = []
        for provider in self._providers:
            try:
                proxies = await provider.fetch_proxies()
                logger.info("Fetched %d proxies from %s", len(proxies), provider.name)
                all_proxies.extend(proxies)
            except Exception as exc:
                logger.warning("Failed to fetch from %s: %s", provider.name, exc)
        self._proxies = self._deduplicate(all_proxies)
        self._current_index = 0
        return len(self._proxies)

    # -- Testing -------------------------------------------------------------

    async def test_proxy(self, proxy: ProxyInfo) -> bool:
        """Test whether *proxy* can reach :attr:`_test_url`.

        Updates ``proxy.is_working`` and ``proxy.last_tested``.
        Returns *True* if the test request succeeds.
        """
        try:
            async with httpx.AsyncClient(
                proxy=proxy.url,
                timeout=httpx.Timeout(_TEST_TIMEOUT),
            ) as client:
                resp = await client.get(self._test_url)
                resp.raise_for_status()
            self.mark_working(proxy)
            return True
        except Exception:
            self.mark_failed(proxy)
            return False

    # -- Rotation ------------------------------------------------------------

    def get_next(self) -> ProxyInfo | None:
        """Return the next available proxy via round-robin.

        Skips proxies that have been explicitly marked as non-working
        (``is_working is False``).  Returns *None* if no candidates remain.
        """
        if not self._proxies:
            return None

        candidates = len(self._proxies)
        for _ in range(candidates):
            proxy = self._proxies[self._current_index % candidates]
            self._current_index = (self._current_index + 1) % candidates
            if proxy.is_working is not False:
                return proxy
        return None

    # -- Health tracking -----------------------------------------------------

    def mark_failed(self, proxy: ProxyInfo) -> None:
        """Record a failure for *proxy*.  Disables it after *_MAX_FAIL_COUNT* failures."""
        proxy.fail_count += 1
        if proxy.fail_count >= _MAX_FAIL_COUNT:
            proxy.is_working = False

    def mark_working(self, proxy: ProxyInfo) -> None:
        """Record a successful use of *proxy*."""
        proxy.is_working = True
        proxy.fail_count = 0
        proxy.last_tested = datetime.now()

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _deduplicate(proxies: list[ProxyInfo]) -> list[ProxyInfo]:
        """Remove duplicate proxies (same ip:port)."""
        seen: set[str] = set()
        unique: list[ProxyInfo] = []
        for p in proxies:
            key = f"{p.ip}:{p.port}"
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

    @property
    def available_count(self) -> int:
        """Number of proxies that have not been marked as failed."""
        return len([p for p in self._proxies if p.is_working is not False])

    @property
    def proxies(self) -> list[ProxyInfo]:
        """All proxies currently held by the manager (read-only view)."""
        return list(self._proxies)
