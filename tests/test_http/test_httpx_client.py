"""Tests for the httpx-based HTTP client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from power_scrapper.config import DEFAULT_USER_AGENT
from power_scrapper.errors import HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient
from power_scrapper.http.httpx_client import HttpxClient


class TestHttpxClientCreation:
    """Test client instantiation and configuration."""

    def test_tier_name(self) -> None:
        client = HttpxClient()
        assert client.tier_name == "httpx"

    def test_implements_interface(self) -> None:
        client = HttpxClient()
        assert isinstance(client, IHttpClient)

    def test_default_user_agent(self) -> None:
        client = HttpxClient()
        assert client._client.headers["user-agent"] == DEFAULT_USER_AGENT

    def test_custom_user_agent(self) -> None:
        client = HttpxClient(user_agent="CustomBot/1.0")
        assert client._client.headers["user-agent"] == "CustomBot/1.0"

    def test_custom_timeout(self) -> None:
        client = HttpxClient(timeout=30.0)
        assert client._client.timeout.connect == 30.0

    def test_follow_redirects_enabled(self) -> None:
        client = HttpxClient()
        assert client._client.follow_redirects is True


class TestHttpxClientGet:
    """Test the async get() method."""

    async def test_get_success(self) -> None:
        client = HttpxClient()
        mock_response = httpx.Response(
            status_code=200,
            text="OK",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", "https://example.com"),
        )

        mock_get = AsyncMock(return_value=mock_response)
        with patch.object(client._client, "get", mock_get):
            resp = await client.get("https://example.com")

        assert isinstance(resp, HttpResponse)
        assert resp.status_code == 200
        assert resp.text == "OK"
        assert resp.url == "https://example.com"
        assert "content-type" in resp.headers

    async def test_get_wraps_http_error(self) -> None:
        client = HttpxClient()

        with (
            patch.object(
                client._client,
                "get",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("connection refused"),
            ),
            pytest.raises(HttpClientError, match="httpx GET.*failed"),
        ):
            await client.get("https://unreachable.test")

    async def test_get_passes_extra_headers(self) -> None:
        client = HttpxClient()
        mock_response = httpx.Response(
            status_code=200,
            text="",
            request=httpx.Request("GET", "https://example.com"),
        )

        mock_get = AsyncMock(return_value=mock_response)
        with patch.object(client._client, "get", mock_get):
            await client.get("https://example.com", headers={"Accept": "application/json"})

        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"Accept": "application/json"}


class TestHttpxClientClose:
    """Test the close() method."""

    async def test_close_calls_aclose(self) -> None:
        client = HttpxClient()
        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_aclose:
            await client.close()
            mock_aclose.assert_awaited_once()


class TestHttpResponse:
    """Test the HttpResponse dataclass."""

    def test_fields(self) -> None:
        resp = HttpResponse(
            status_code=404,
            text="Not Found",
            headers={"server": "nginx"},
            url="https://example.com/missing",
        )
        assert resp.status_code == 404
        assert resp.text == "Not Found"
        assert resp.headers == {"server": "nginx"}
        assert resp.url == "https://example.com/missing"
