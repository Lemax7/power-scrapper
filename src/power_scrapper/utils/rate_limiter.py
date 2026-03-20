"""Adaptive rate limiting with human-like timing patterns."""

from __future__ import annotations

import asyncio
import logging
import random
import time

logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    """Rate limiter with exponential backoff and human-like delays.

    Features:
    - **Poisson-distributed delays** that mimic human reading patterns
    - **Exponential backoff** on 429/403 responses (15s -> 30s -> 60s -> skip)
    - **Per-domain backoff tracking** so one blocked domain doesn't slow all requests
    - **AI Labyrinth detection** for Cloudflare honeypot links
    """

    # Backoff stages: 15s, 30s, 60s, then give up.
    _BACKOFF_STAGES = [15.0, 30.0, 60.0]

    def __init__(
        self,
        *,
        base_delay: float = 5.0,
        max_delay: float = 15.0,
    ) -> None:
        self._base_delay = base_delay
        self._max_delay = max_delay
        # domain -> current backoff level (0 = no backoff, 1-3 = stages)
        self._domain_backoff: dict[str, int] = {}
        self._last_request_time: dict[str, float] = {}

    def human_delay(self) -> float:
        """Return a Poisson-distributed delay that mimics human reading patterns.

        The mean is ``(base_delay + max_delay) / 2`` with natural variation.
        Occasionally returns longer delays to simulate distracted reading.
        """
        mean = (self._base_delay + self._max_delay) / 2
        # Poisson-ish via exponential distribution (continuous analog)
        delay = random.expovariate(1.0 / mean)
        # Clamp to reasonable range
        return max(self._base_delay * 0.5, min(delay, self._max_delay * 2.0))

    async def wait(self, domain: str | None = None) -> None:
        """Wait an appropriate amount of time before making a request.

        If *domain* has active backoff, waits the backoff duration instead.
        """
        if domain and domain in self._domain_backoff:
            level = self._domain_backoff[domain]
            if level > 0 and level <= len(self._BACKOFF_STAGES):
                backoff = self._BACKOFF_STAGES[level - 1]
                logger.info("Backoff level %d for %s: waiting %.1fs", level, domain, backoff)
                await asyncio.sleep(backoff)
                return

        delay = self.human_delay()
        logger.debug("Rate limit delay: %.1fs", delay)
        await asyncio.sleep(delay)

    def record_success(self, domain: str) -> None:
        """Record a successful request -- reset backoff for domain."""
        self._domain_backoff.pop(domain, None)
        self._last_request_time[domain] = time.time()

    def record_block(self, domain: str) -> bool:
        """Record a blocked request (429/403).

        Returns ``True`` if we should retry, ``False`` if all backoff stages
        are exhausted and we should skip this domain.
        """
        level = self._domain_backoff.get(domain, 0) + 1
        self._domain_backoff[domain] = level

        if level > len(self._BACKOFF_STAGES):
            logger.warning("All backoff stages exhausted for %s, skipping", domain)
            return False

        logger.info(
            "Block detected for %s, escalating to backoff level %d (%.1fs)",
            domain,
            level,
            self._BACKOFF_STAGES[level - 1],
        )
        return True

    def should_skip(self, domain: str) -> bool:
        """Return ``True`` if this domain has exhausted all backoff stages."""
        level = self._domain_backoff.get(domain, 0)
        return level > len(self._BACKOFF_STAGES)

    @staticmethod
    def is_ai_labyrinth_link(url: str, rel: str = "", text: str = "") -> bool:
        """Detect Cloudflare AI Labyrinth honeypot links.

        These are AI-generated pages injected by Cloudflare to trap bots.
        Indicators:
        - ``rel="nofollow"`` on links that look like content
        - URLs with suspicious patterns (long random paths, unusual domains)
        - Link text that is generic/AI-generated
        """
        if "nofollow" in rel.lower():
            # Check for suspiciously random URL paths
            parts = url.rstrip("/").split("/")
            if len(parts) > 5:
                # Long paths with random-looking segments
                last_segments = parts[-3:]
                random_chars = sum(
                    1 for seg in last_segments
                    if len(seg) > 20 or (seg and not seg[0].isalpha())
                )
                if random_chars >= 2:
                    return True

        # Check for known Cloudflare honeypot patterns
        honeypot_patterns = [
            "/cdn-cgi/",
            "challenge-platform",
            "__cf_chl_",
        ]
        url_lower = url.lower()
        return any(p in url_lower for p in honeypot_patterns)
