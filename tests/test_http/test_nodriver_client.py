"""Tests for the NoDriver HTTP client."""

from __future__ import annotations

import pytest

from power_scrapper.http.base import IHttpClient
from power_scrapper.http.nodriver_client import NoDriverClient


class TestNoDriverClient:
    def test_implements_interface(self) -> None:
        client = NoDriverClient()
        assert isinstance(client, IHttpClient)

    def test_tier_name(self) -> None:
        assert NoDriverClient().tier_name == "nodriver"

    def test_lazy_init(self) -> None:
        client = NoDriverClient()
        assert client._browser is None

    def test_default_headless(self) -> None:
        client = NoDriverClient()
        assert client._headless is True

    def test_custom_timeout(self) -> None:
        client = NoDriverClient(timeout=30.0)
        assert client._timeout == 30.0

    async def test_close_when_no_browser(self) -> None:
        client = NoDriverClient()
        # Should not raise.
        await client.close()
        assert client._browser is None

    async def test_get_cookies_when_no_browser(self) -> None:
        client = NoDriverClient()
        cookies = await client.get_cookies()
        assert cookies == []
