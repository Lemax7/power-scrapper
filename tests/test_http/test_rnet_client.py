"""Tests for the rnet HTTP client."""

from __future__ import annotations

import pytest

from power_scrapper.http.base import IHttpClient
from power_scrapper.http.rnet_client import RnetClient


class TestRnetClient:
    def test_implements_interface(self) -> None:
        client = RnetClient()
        assert isinstance(client, IHttpClient)

    def test_tier_name(self) -> None:
        assert RnetClient().tier_name == "rnet"

    def test_default_impersonate(self) -> None:
        client = RnetClient()
        assert client._impersonate == "chrome_136"

    def test_custom_impersonate(self) -> None:
        client = RnetClient(impersonate="firefox_139")
        assert client._impersonate == "firefox_139"

    def test_lazy_init(self) -> None:
        client = RnetClient()
        assert client._client is None

    async def test_close_resets_client(self) -> None:
        client = RnetClient()
        client._client = "something"
        await client.close()
        assert client._client is None
