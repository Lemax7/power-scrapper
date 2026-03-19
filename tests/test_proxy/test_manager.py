"""Tests for ProxyManager."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

from power_scrapper.proxy.base import IProxyProvider, ProxyInfo
from power_scrapper.proxy.manager import ProxyManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeProvider(IProxyProvider):
    """Simple provider that returns a pre-set proxy list."""

    def __init__(self, provider_name: str, proxies: list[ProxyInfo]) -> None:
        self._name = provider_name
        self._proxies = proxies

    @property
    def name(self) -> str:
        return self._name

    async def fetch_proxies(self) -> list[ProxyInfo]:
        return list(self._proxies)


class _FailingProvider(IProxyProvider):
    """Provider that always raises."""

    @property
    def name(self) -> str:
        return "failing"

    async def fetch_proxies(self) -> list[ProxyInfo]:
        raise RuntimeError("simulated network error")


def _proxy(ip: str, port: int = 8080, **kwargs) -> ProxyInfo:  # noqa: ANN003
    return ProxyInfo(ip=ip, port=port, **kwargs)


# ---------------------------------------------------------------------------
# Fetch + aggregation
# ---------------------------------------------------------------------------


class TestFetchAll:
    async def test_aggregates_from_multiple_providers(self) -> None:
        p1 = _FakeProvider("a", [_proxy("1.1.1.1"), _proxy("2.2.2.2")])
        p2 = _FakeProvider("b", [_proxy("3.3.3.3")])
        mgr = ProxyManager(providers=[p1, p2])

        total = await mgr.fetch_all()

        assert total == 3
        ips = {p.ip for p in mgr.proxies}
        assert ips == {"1.1.1.1", "2.2.2.2", "3.3.3.3"}

    async def test_skips_failing_provider(self) -> None:
        good = _FakeProvider("good", [_proxy("1.1.1.1")])
        bad = _FailingProvider()
        mgr = ProxyManager(providers=[good, bad])

        total = await mgr.fetch_all()

        assert total == 1
        assert mgr.proxies[0].ip == "1.1.1.1"

    async def test_returns_zero_when_all_fail(self) -> None:
        mgr = ProxyManager(providers=[_FailingProvider()])
        total = await mgr.fetch_all()
        assert total == 0


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    async def test_removes_duplicates_by_ip_port(self) -> None:
        p1 = _FakeProvider("a", [_proxy("1.1.1.1", 8080), _proxy("1.1.1.1", 8080)])
        p2 = _FakeProvider("b", [_proxy("1.1.1.1", 8080), _proxy("2.2.2.2", 3128)])
        mgr = ProxyManager(providers=[p1, p2])

        total = await mgr.fetch_all()

        assert total == 2
        ips_ports = {(p.ip, p.port) for p in mgr.proxies}
        assert ips_ports == {("1.1.1.1", 8080), ("2.2.2.2", 3128)}

    def test_deduplicate_static(self) -> None:
        proxies = [
            _proxy("1.1.1.1", 80),
            _proxy("2.2.2.2", 80),
            _proxy("1.1.1.1", 80),
            _proxy("1.1.1.1", 3128),
        ]
        result = ProxyManager._deduplicate(proxies)
        assert len(result) == 3

    def test_deduplicate_preserves_first_occurrence(self) -> None:
        p1 = _proxy("1.1.1.1", 80, country="US")
        p2 = _proxy("1.1.1.1", 80, country="UK")
        result = ProxyManager._deduplicate([p1, p2])
        assert len(result) == 1
        assert result[0].country == "US"


# ---------------------------------------------------------------------------
# Rotation (get_next)
# ---------------------------------------------------------------------------


class TestGetNext:
    def test_returns_none_when_empty(self) -> None:
        mgr = ProxyManager(providers=[])
        assert mgr.get_next() is None

    async def test_round_robin(self) -> None:
        p = _FakeProvider("a", [_proxy("1.1.1.1"), _proxy("2.2.2.2"), _proxy("3.3.3.3")])
        mgr = ProxyManager(providers=[p])
        await mgr.fetch_all()

        ips = [mgr.get_next().ip for _ in range(6)]  # type: ignore[union-attr]
        assert ips == ["1.1.1.1", "2.2.2.2", "3.3.3.3", "1.1.1.1", "2.2.2.2", "3.3.3.3"]

    async def test_skips_failed_proxies(self) -> None:
        p = _FakeProvider("a", [_proxy("1.1.1.1"), _proxy("2.2.2.2"), _proxy("3.3.3.3")])
        mgr = ProxyManager(providers=[p])
        await mgr.fetch_all()

        # Mark the second proxy as explicitly failed
        mgr.proxies[1].is_working = False
        # But we need to operate on the internal list, not the copy
        mgr._proxies[1].is_working = False

        results: list[str] = []
        for _ in range(4):
            proxy = mgr.get_next()
            assert proxy is not None
            results.append(proxy.ip)
        assert "2.2.2.2" not in results

    async def test_returns_none_when_all_failed(self) -> None:
        p = _FakeProvider("a", [_proxy("1.1.1.1")])
        mgr = ProxyManager(providers=[p])
        await mgr.fetch_all()
        mgr._proxies[0].is_working = False

        assert mgr.get_next() is None

    async def test_untested_proxies_are_eligible(self) -> None:
        """Proxies with ``is_working=None`` (untested) should be returned."""
        p = _FakeProvider("a", [_proxy("1.1.1.1")])
        mgr = ProxyManager(providers=[p])
        await mgr.fetch_all()

        assert mgr._proxies[0].is_working is None
        proxy = mgr.get_next()
        assert proxy is not None
        assert proxy.ip == "1.1.1.1"


# ---------------------------------------------------------------------------
# Health tracking
# ---------------------------------------------------------------------------


class TestMarkFailed:
    def test_increments_fail_count(self) -> None:
        mgr = ProxyManager(providers=[])
        proxy = _proxy("1.1.1.1")
        mgr.mark_failed(proxy)
        assert proxy.fail_count == 1
        assert proxy.is_working is None  # not disabled yet

    def test_disables_after_three_failures(self) -> None:
        mgr = ProxyManager(providers=[])
        proxy = _proxy("1.1.1.1")
        mgr.mark_failed(proxy)
        mgr.mark_failed(proxy)
        assert proxy.is_working is None  # still not disabled at 2
        mgr.mark_failed(proxy)
        assert proxy.fail_count == 3
        assert proxy.is_working is False

    def test_disables_beyond_three_failures(self) -> None:
        mgr = ProxyManager(providers=[])
        proxy = _proxy("1.1.1.1")
        for _ in range(5):
            mgr.mark_failed(proxy)
        assert proxy.is_working is False
        assert proxy.fail_count == 5


class TestMarkWorking:
    def test_resets_state(self) -> None:
        mgr = ProxyManager(providers=[])
        proxy = _proxy("1.1.1.1")
        proxy.fail_count = 2
        proxy.is_working = None

        before = datetime.now()
        mgr.mark_working(proxy)

        assert proxy.is_working is True
        assert proxy.fail_count == 0
        assert proxy.last_tested is not None
        assert proxy.last_tested >= before

    def test_resets_after_failure(self) -> None:
        mgr = ProxyManager(providers=[])
        proxy = _proxy("1.1.1.1")
        proxy.fail_count = 3
        proxy.is_working = False

        mgr.mark_working(proxy)

        assert proxy.is_working is True
        assert proxy.fail_count == 0


# ---------------------------------------------------------------------------
# available_count
# ---------------------------------------------------------------------------


class TestAvailableCount:
    async def test_all_untested(self) -> None:
        p = _FakeProvider("a", [_proxy("1.1.1.1"), _proxy("2.2.2.2")])
        mgr = ProxyManager(providers=[p])
        await mgr.fetch_all()
        assert mgr.available_count == 2

    async def test_excludes_failed(self) -> None:
        p = _FakeProvider("a", [_proxy("1.1.1.1"), _proxy("2.2.2.2"), _proxy("3.3.3.3")])
        mgr = ProxyManager(providers=[p])
        await mgr.fetch_all()
        mgr._proxies[0].is_working = False
        mgr._proxies[2].is_working = True
        assert mgr.available_count == 2

    def test_empty(self) -> None:
        mgr = ProxyManager(providers=[])
        assert mgr.available_count == 0


# ---------------------------------------------------------------------------
# test_proxy
# ---------------------------------------------------------------------------


class TestTestProxy:
    async def test_marks_working_on_success(self) -> None:
        mgr = ProxyManager(providers=[])
        proxy = _proxy("1.1.1.1")

        with patch("power_scrapper.proxy.manager.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = lambda: None
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await mgr.test_proxy(proxy)

        assert result is True
        assert proxy.is_working is True
        assert proxy.fail_count == 0

    async def test_marks_failed_on_error(self) -> None:
        mgr = ProxyManager(providers=[])
        proxy = _proxy("1.1.1.1")

        with patch("power_scrapper.proxy.manager.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await mgr.test_proxy(proxy)

        assert result is False
        assert proxy.fail_count == 1
