"""Auto-escalating tiered HTTP client."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from power_scrapper.errors import AllTiersExhaustedError, HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient

logger = logging.getLogger(__name__)

# Strings that indicate Cloudflare or similar anti-bot challenges.
_BLOCKED_INDICATORS: tuple[str, ...] = (
    "Attention Required",
    "Please Wait",
    "cf-browser-verification",
    "Just a moment",
    "Checking your browser",
    "Enable JavaScript and cookies to continue",
    "Verify you are human",
    "Access denied",
    "cf-challenge-running",
    "ray ID",
)


def _looks_blocked(response: HttpResponse) -> bool:
    """Return ``True`` if the response looks like a bot-detection block.

    Checks for common Cloudflare challenge indicators, CAPTCHAs, and
    other anti-bot signals in the response body.
    """
    if not response.text:
        return False

    # Short responses with block-like status codes are suspicious.
    text_lower = response.text.lower()
    for indicator in _BLOCKED_INDICATORS:
        if indicator.lower() in text_lower:
            return True

    return False


def _extract_domain(url: str) -> str:
    """Extract the domain (netloc) from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:  # noqa: BLE001
        return url


class TieredHttpClient(IHttpClient):
    """Tries HTTP tiers in order, auto-escalates on failure.

    Tier 1: httpx (fast, HTTP/2)
    Tier 2: curl_cffi (TLS fingerprinting)
    Tier 3: patchright (full browser)

    Remembers per-domain tier preferences for subsequent requests so a
    domain that required tier 2 last time starts at tier 2 next time.
    """

    def __init__(
        self,
        *,
        tiers: list[IHttpClient] | None = None,
        timeout: float = 10.0,
        proxy: str | None = None,
    ) -> None:
        self._tiers = tiers if tiers is not None else self._build_default_tiers(
            timeout=timeout, proxy=proxy,
        )
        self._domain_tier: dict[str, int] = {}

    @staticmethod
    def _build_default_tiers(
        *,
        timeout: float = 10.0,
        proxy: str | None = None,
    ) -> list[IHttpClient]:
        """Build the default tier list, skipping unavailable dependencies."""
        tiers: list[IHttpClient] = []

        # Tier 1: httpx -- always available (hard dependency).
        from power_scrapper.http.httpx_client import HttpxClient

        tiers.append(HttpxClient(timeout=timeout, proxy=proxy))

        # Tier 2: curl_cffi -- optional.
        try:
            from power_scrapper.http.curl_cffi_client import CurlCffiClient

            tiers.append(CurlCffiClient(timeout=timeout, proxy=proxy))
        except Exception:  # noqa: BLE001
            logger.debug("curl_cffi not available, skipping tier 2")

        # Tier 3: patchright -- optional.
        try:
            from power_scrapper.http.patchright_client import PatchrightClient

            tiers.append(PatchrightClient(timeout=timeout, proxy=proxy))
        except Exception:  # noqa: BLE001
            logger.debug("patchright not available, skipping tier 3")

        return tiers

    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Try each tier in order; escalate on failure or blocking.

        Raises :class:`AllTiersExhaustedError` if every tier fails.
        """
        domain = _extract_domain(url)
        start_tier = self._domain_tier.get(domain, 0)

        for i in range(start_tier, len(self._tiers)):
            tier = self._tiers[i]
            try:
                response = await tier.get(url, headers=headers)

                # Check for Cloudflare / blocking patterns.
                if response.status_code == 403 or _looks_blocked(response):
                    logger.info(
                        "Tier %s got blocked for %s, escalating",
                        tier.tier_name,
                        domain,
                    )
                    continue

                # Success -- remember which tier worked for this domain.
                self._domain_tier[domain] = i
                return response
            except HttpClientError:
                logger.info(
                    "Tier %s failed for %s, escalating",
                    tier.tier_name,
                    domain,
                )
                continue

        raise AllTiersExhaustedError(f"All tiers failed for {url}")

    async def close(self) -> None:
        """Close all underlying tier clients."""
        for tier in self._tiers:
            try:
                await tier.close()
            except Exception:  # noqa: BLE001
                logger.debug("Error closing tier %s", tier.tier_name, exc_info=True)

    @property
    def tier_name(self) -> str:  # noqa: D401
        """Client tier identifier."""
        return "tiered"
