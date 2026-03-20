"""Tests for TieredHttpClient with cache integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from power_scrapper.http.base import HttpResponse, IHttpClient
from power_scrapper.http.tiered import TieredHttpClient
from power_scrapper.utils.cache import ResponseCache


def _make_mock_tier(name: str, *, response: HttpResponse | None = None) -> IHttpClient:
    mock = MagicMock(spec=IHttpClient)
    mock.tier_name = name
    mock.get = AsyncMock(
        return_value=response
        or HttpResponse(status_code=200, text="OK", headers={}, url="https://example.com")
    )
    mock.close = AsyncMock()
    return mock


class TestTieredWithCache:
    async def test_cache_hit_skips_tiers(self, tmp_path: Path) -> None:
        cache = ResponseCache(db_path=tmp_path / "test.db", ttl_hours=24)
        cache.put("https://example.com", "cached body", 200)

        t1 = _make_mock_tier("tier1")
        client = TieredHttpClient(tiers=[t1], cache=cache)

        resp = await client.get("https://example.com")
        assert resp.text == "cached body"
        assert resp.status_code == 200
        t1.get.assert_not_awaited()  # Tier was never called.

        cache.close()

    async def test_cache_miss_falls_through(self, tmp_path: Path) -> None:
        cache = ResponseCache(db_path=tmp_path / "test.db", ttl_hours=24)

        t1 = _make_mock_tier("tier1")
        client = TieredHttpClient(tiers=[t1], cache=cache)

        resp = await client.get("https://example.com")
        assert resp.text == "OK"
        t1.get.assert_awaited_once()

        # The response should now be cached.
        cached = cache.get("https://example.com")
        assert cached is not None
        body, status = cached
        assert body == "OK"
        assert status == 200

        cache.close()

    async def test_no_cache_works(self) -> None:
        t1 = _make_mock_tier("tier1")
        client = TieredHttpClient(tiers=[t1], cache=None)

        resp = await client.get("https://example.com")
        assert resp.status_code == 200
        t1.get.assert_awaited_once()
