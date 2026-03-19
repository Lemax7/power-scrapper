"""Tests for proxy source providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from power_scrapper.proxy.base import ProxyProtocol
from power_scrapper.proxy.sources import (
    GeoNodeProvider,
    GitHubListProvider,
    ProxyScrapeProvider,
    _parse_text_proxy_list,
)

# ---------------------------------------------------------------------------
# GeoNodeProvider
# ---------------------------------------------------------------------------


class TestGeoNodeProvider:
    def test_name(self) -> None:
        assert GeoNodeProvider().name == "geonode"

    async def test_parses_json_response(self) -> None:
        payload = {
            "data": [
                {"ip": "1.2.3.4", "port": "8080", "protocols": ["http", "https"], "country": "US"},
                {"ip": "5.6.7.8", "port": "3128", "protocols": ["https"], "country": "DE"},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()

        provider = GeoNodeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert len(proxies) == 2
        assert proxies[0].ip == "1.2.3.4"
        assert proxies[0].port == 8080
        assert proxies[0].protocol == ProxyProtocol.HTTPS  # https preferred over http
        assert proxies[0].country == "US"
        assert proxies[1].ip == "5.6.7.8"
        assert proxies[1].port == 3128
        assert proxies[1].protocol == ProxyProtocol.HTTPS
        assert proxies[1].country == "DE"

    async def test_picks_http_when_only_http(self) -> None:
        payload = {
            "data": [
                {"ip": "1.2.3.4", "port": "80", "protocols": ["http"], "country": "RU"},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()

        provider = GeoNodeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert proxies[0].protocol == ProxyProtocol.HTTP

    async def test_skips_entries_without_ip_or_port(self) -> None:
        payload = {
            "data": [
                {"ip": "", "port": "8080", "protocols": ["http"], "country": "US"},
                {"ip": "1.1.1.1", "port": "", "protocols": ["http"], "country": "US"},
                {"ip": "2.2.2.2", "port": "3128", "protocols": ["http"], "country": "US"},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()

        provider = GeoNodeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert len(proxies) == 1
        assert proxies[0].ip == "2.2.2.2"

    async def test_skips_entries_with_invalid_port(self) -> None:
        payload = {
            "data": [
                {"ip": "1.1.1.1", "port": "notanumber", "protocols": ["http"], "country": "US"},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()

        provider = GeoNodeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert len(proxies) == 0

    async def test_returns_empty_on_network_error(self) -> None:
        provider = GeoNodeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert proxies == []

    async def test_handles_empty_data(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status = MagicMock()

        provider = GeoNodeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert proxies == []

    async def test_handles_missing_data_key(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        provider = GeoNodeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert proxies == []


# ---------------------------------------------------------------------------
# ProxyScrapeProvider
# ---------------------------------------------------------------------------


class TestProxyScrapeProvider:
    def test_name(self) -> None:
        assert ProxyScrapeProvider().name == "proxyscrape"

    async def test_parses_text_response(self) -> None:
        text = "1.2.3.4:8080\n5.6.7.8:3128\n9.10.11.12:80\n"
        mock_resp = AsyncMock()
        mock_resp.text = text
        mock_resp.raise_for_status = lambda: None

        provider = ProxyScrapeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert len(proxies) == 3
        assert proxies[0].ip == "1.2.3.4"
        assert proxies[0].port == 8080
        assert proxies[1].ip == "5.6.7.8"
        assert proxies[1].port == 3128
        assert proxies[2].ip == "9.10.11.12"
        assert proxies[2].port == 80

    async def test_returns_empty_on_error(self) -> None:
        provider = ProxyScrapeProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert proxies == []


# ---------------------------------------------------------------------------
# GitHubListProvider
# ---------------------------------------------------------------------------


class TestGitHubListProvider:
    def test_name(self) -> None:
        assert GitHubListProvider().name == "github_list"

    async def test_parses_text_response(self) -> None:
        text = "10.0.0.1:8888\n192.168.1.1:3128\n"
        mock_resp = AsyncMock()
        mock_resp.text = text
        mock_resp.raise_for_status = lambda: None

        provider = GitHubListProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert len(proxies) == 2
        assert proxies[0].ip == "10.0.0.1"
        assert proxies[0].port == 8888
        assert proxies[1].ip == "192.168.1.1"
        assert proxies[1].port == 3128

    async def test_returns_empty_on_error(self) -> None:
        provider = GitHubListProvider()
        with patch("power_scrapper.proxy.sources.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            proxies = await provider.fetch_proxies()

        assert proxies == []


# ---------------------------------------------------------------------------
# _parse_text_proxy_list helper
# ---------------------------------------------------------------------------


class TestParseTextProxyList:
    def test_standard_list(self) -> None:
        text = "1.2.3.4:80\n5.6.7.8:3128\n"
        result = _parse_text_proxy_list(text)
        assert len(result) == 2
        assert result[0].ip == "1.2.3.4"
        assert result[0].port == 80

    def test_handles_blank_lines(self) -> None:
        text = "1.2.3.4:80\n\n\n5.6.7.8:3128\n\n"
        result = _parse_text_proxy_list(text)
        assert len(result) == 2

    def test_handles_whitespace(self) -> None:
        text = "  1.2.3.4:80  \n  5.6.7.8:3128  \n"
        result = _parse_text_proxy_list(text)
        assert len(result) == 2
        assert result[0].ip == "1.2.3.4"

    def test_skips_invalid_port(self) -> None:
        text = "1.2.3.4:abc\n5.6.7.8:3128\n"
        result = _parse_text_proxy_list(text)
        assert len(result) == 1
        assert result[0].ip == "5.6.7.8"

    def test_skips_lines_without_colon(self) -> None:
        text = "some random text\n1.2.3.4:80\n"
        result = _parse_text_proxy_list(text)
        assert len(result) == 1

    def test_empty_string(self) -> None:
        assert _parse_text_proxy_list("") == []

    def test_skips_lines_with_multiple_colons(self) -> None:
        text = "1.2.3.4:80:extra\n5.6.7.8:3128\n"
        result = _parse_text_proxy_list(text)
        assert len(result) == 1
        assert result[0].ip == "5.6.7.8"

    def test_default_protocol_is_http(self) -> None:
        result = _parse_text_proxy_list("1.2.3.4:80\n")
        assert result[0].protocol == ProxyProtocol.HTTP
