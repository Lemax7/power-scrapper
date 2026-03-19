"""Tests for the tiered HTTP client and helper utilities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from power_scrapper.errors import AllTiersExhaustedError, HttpClientError
from power_scrapper.http.base import HttpResponse, IHttpClient
from power_scrapper.http.tiered import (
    TieredHttpClient,
    _extract_domain,
    _looks_blocked,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_tier(
    name: str,
    *,
    response: HttpResponse | None = None,
    error: Exception | None = None,
) -> IHttpClient:
    """Create a mock :class:`IHttpClient` that returns *response* or raises *error*."""
    mock = MagicMock(spec=IHttpClient)
    mock.tier_name = name

    if error is not None:
        mock.get = AsyncMock(side_effect=error)
    elif response is not None:
        mock.get = AsyncMock(return_value=response)
    else:
        mock.get = AsyncMock(return_value=HttpResponse(
            status_code=200, text="OK", headers={}, url="https://example.com",
        ))

    mock.close = AsyncMock()
    return mock


def _ok_response(url: str = "https://example.com", text: str = "OK") -> HttpResponse:
    return HttpResponse(status_code=200, text=text, headers={}, url=url)


def _blocked_response(url: str = "https://example.com") -> HttpResponse:
    return HttpResponse(
        status_code=403,
        text="Attention Required! | Cloudflare",
        headers={},
        url=url,
    )


# ---------------------------------------------------------------------------
# _looks_blocked
# ---------------------------------------------------------------------------

class TestLooksBlocked:
    """Test the block-detection helper."""

    def test_empty_text_not_blocked(self) -> None:
        resp = HttpResponse(status_code=200, text="", headers={}, url="https://x.com")
        assert _looks_blocked(resp) is False

    def test_normal_page_not_blocked(self) -> None:
        resp = HttpResponse(
            status_code=200,
            text="<html><body>Hello world</body></html>",
            headers={},
            url="https://x.com",
        )
        assert _looks_blocked(resp) is False

    @pytest.mark.parametrize(
        "indicator",
        [
            "Attention Required",
            "Just a moment",
            "cf-browser-verification",
            "Checking your browser",
            "Please Wait",
            "Verify you are human",
            "Access denied",
        ],
    )
    def test_detects_known_indicators(self, indicator: str) -> None:
        resp = HttpResponse(
            status_code=200,
            text=f"<html><body>{indicator}</body></html>",
            headers={},
            url="https://x.com",
        )
        assert _looks_blocked(resp) is True

    def test_case_insensitive(self) -> None:
        resp = HttpResponse(
            status_code=200,
            text="<html>just a moment please</html>",
            headers={},
            url="https://x.com",
        )
        assert _looks_blocked(resp) is True


# ---------------------------------------------------------------------------
# _extract_domain
# ---------------------------------------------------------------------------

class TestExtractDomain:
    """Test domain extraction from URLs."""

    def test_simple_url(self) -> None:
        assert _extract_domain("https://example.com/path") == "example.com"

    def test_url_with_port(self) -> None:
        assert _extract_domain("https://example.com:8080/path") == "example.com:8080"

    def test_url_with_subdomain(self) -> None:
        assert _extract_domain("https://sub.example.com/path") == "sub.example.com"

    def test_bad_url_returns_input(self) -> None:
        # urlparse will set netloc to '' for bare strings; fallback returns input.
        assert _extract_domain("not-a-url") == "not-a-url"


# ---------------------------------------------------------------------------
# TieredHttpClient
# ---------------------------------------------------------------------------

class TestTieredEscalation:
    """Test that the client escalates through tiers on failure."""

    async def test_first_tier_succeeds(self) -> None:
        t1 = _make_mock_tier("tier1", response=_ok_response())
        t2 = _make_mock_tier("tier2", response=_ok_response())

        client = TieredHttpClient(tiers=[t1, t2])
        resp = await client.get("https://example.com")

        assert resp.status_code == 200
        t1.get.assert_awaited_once()
        t2.get.assert_not_awaited()

    async def test_escalates_on_http_error(self) -> None:
        t1 = _make_mock_tier("tier1", error=HttpClientError("fail"))
        t2 = _make_mock_tier("tier2", response=_ok_response())

        client = TieredHttpClient(tiers=[t1, t2])
        resp = await client.get("https://example.com")

        assert resp.status_code == 200
        t1.get.assert_awaited_once()
        t2.get.assert_awaited_once()

    async def test_escalates_on_403(self) -> None:
        blocked = HttpResponse(status_code=403, text="Forbidden", headers={}, url="https://example.com")
        t1 = _make_mock_tier("tier1", response=blocked)
        t2 = _make_mock_tier("tier2", response=_ok_response())

        client = TieredHttpClient(tiers=[t1, t2])
        resp = await client.get("https://example.com")

        assert resp.status_code == 200
        t1.get.assert_awaited_once()
        t2.get.assert_awaited_once()

    async def test_escalates_on_blocked_content(self) -> None:
        blocked = HttpResponse(
            status_code=200,
            text="<html>Just a moment... Checking your browser</html>",
            headers={},
            url="https://example.com",
        )
        t1 = _make_mock_tier("tier1", response=blocked)
        t2 = _make_mock_tier("tier2", response=_ok_response())

        client = TieredHttpClient(tiers=[t1, t2])
        resp = await client.get("https://example.com")

        assert resp.status_code == 200

    async def test_all_tiers_exhausted(self) -> None:
        t1 = _make_mock_tier("tier1", error=HttpClientError("fail1"))
        t2 = _make_mock_tier("tier2", error=HttpClientError("fail2"))

        client = TieredHttpClient(tiers=[t1, t2])

        with pytest.raises(AllTiersExhaustedError, match="All tiers failed"):
            await client.get("https://example.com")

    async def test_all_tiers_blocked(self) -> None:
        blocked = _blocked_response()
        t1 = _make_mock_tier("tier1", response=blocked)
        t2 = _make_mock_tier("tier2", response=blocked)

        client = TieredHttpClient(tiers=[t1, t2])

        with pytest.raises(AllTiersExhaustedError):
            await client.get("https://example.com")


class TestDomainTierCaching:
    """Test that the tiered client remembers which tier worked per domain."""

    async def test_remembers_successful_tier(self) -> None:
        t1 = _make_mock_tier("tier1", error=HttpClientError("fail"))
        t2 = _make_mock_tier("tier2", response=_ok_response())

        client = TieredHttpClient(tiers=[t1, t2])

        # First request -- escalates from tier 0 to tier 1.
        await client.get("https://example.com/page1")
        assert client._domain_tier.get("example.com") == 1

        # Second request to same domain starts at tier 1 directly.
        await client.get("https://example.com/page2")

        # tier1 was only called once (during the first request).
        assert t1.get.await_count == 1
        # tier2 was called twice (once per request).
        assert t2.get.await_count == 2

    async def test_different_domains_tracked_independently(self) -> None:
        t1 = _make_mock_tier("tier1", error=HttpClientError("fail"))
        ok_resp_a = HttpResponse(status_code=200, text="A", headers={}, url="https://a.com")
        ok_resp_b = HttpResponse(status_code=200, text="B", headers={}, url="https://b.com")
        t2 = _make_mock_tier("tier2")
        t2.get = AsyncMock(side_effect=[ok_resp_a, ok_resp_b])

        client = TieredHttpClient(tiers=[t1, t2])

        await client.get("https://a.com/path")
        await client.get("https://b.com/path")

        assert client._domain_tier.get("a.com") == 1
        assert client._domain_tier.get("b.com") == 1

    async def test_tier0_success_not_polluted(self) -> None:
        """Tier 0 success should be remembered as tier 0."""
        t1 = _make_mock_tier("tier1", response=_ok_response())
        t2 = _make_mock_tier("tier2")

        client = TieredHttpClient(tiers=[t1, t2])
        await client.get("https://easy.com/page")

        assert client._domain_tier.get("easy.com") == 0


class TestTieredClientMeta:
    """Test non-request aspects of TieredHttpClient."""

    def test_tier_name(self) -> None:
        client = TieredHttpClient(tiers=[])
        assert client.tier_name == "tiered"

    async def test_close_calls_all_tiers(self) -> None:
        t1 = _make_mock_tier("tier1")
        t2 = _make_mock_tier("tier2")

        client = TieredHttpClient(tiers=[t1, t2])
        await client.close()

        t1.close.assert_awaited_once()
        t2.close.assert_awaited_once()

    async def test_close_tolerates_tier_errors(self) -> None:
        t1 = _make_mock_tier("tier1")
        t1.close = AsyncMock(side_effect=RuntimeError("boom"))
        t2 = _make_mock_tier("tier2")

        client = TieredHttpClient(tiers=[t1, t2])
        # Should not raise.
        await client.close()
        t2.close.assert_awaited_once()

    def test_implements_interface(self) -> None:
        client = TieredHttpClient(tiers=[])
        assert isinstance(client, IHttpClient)


class TestBuildDefaultTiers:
    """Test that _build_default_tiers includes only available dependencies."""

    def test_always_includes_httpx(self) -> None:
        tiers = TieredHttpClient._build_default_tiers()
        assert len(tiers) >= 1
        assert tiers[0].tier_name == "httpx"

    def test_passes_timeout_to_httpx(self) -> None:
        tiers = TieredHttpClient._build_default_tiers(timeout=42.0)
        httpx_tier = tiers[0]
        assert httpx_tier._client.timeout.connect == 42.0
