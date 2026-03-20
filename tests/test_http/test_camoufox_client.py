"""Tests for the Camoufox HTTP client."""

from __future__ import annotations

import pytest

from power_scrapper.http.base import IHttpClient
from power_scrapper.http.camoufox_client import CamoufoxClient


class TestCamoufoxClient:
    def test_implements_interface(self) -> None:
        client = CamoufoxClient()
        assert isinstance(client, IHttpClient)

    def test_tier_name(self) -> None:
        assert CamoufoxClient().tier_name == "camoufox"

    def test_lazy_init(self) -> None:
        client = CamoufoxClient()
        assert client._browser is None

    def test_default_headless(self) -> None:
        client = CamoufoxClient()
        assert client._headless is True

    def test_custom_proxy(self) -> None:
        client = CamoufoxClient(proxy="http://proxy:8080")
        assert client._proxy == "http://proxy:8080"

    async def test_close_when_no_browser(self) -> None:
        client = CamoufoxClient()
        # Should not raise.
        await client.close()
        assert client._browser is None
