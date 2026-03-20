"""Free proxy source providers.

Each provider fetches proxy lists from a public API or raw text file,
parses the response, and returns a list of :class:`ProxyInfo` objects.
Network calls use ``httpx`` directly -- providers are standalone and
do not depend on :class:`IHttpClient`.
"""

from __future__ import annotations

import logging

import httpx

from power_scrapper.proxy.base import IProxyProvider, ProxyInfo, ProxyProtocol

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 15.0  # seconds


class GeoNodeProvider(IProxyProvider):
    """Fetch proxies from the GeoNode API.

    Endpoint returns JSON with a ``data`` array of proxy objects containing
    ``ip``, ``port``, ``protocols``, and ``country`` fields.
    """

    URL = (
        "https://proxylist.geonode.com/api/proxy-list"
        "?limit=50&page=1&sort_by=lastChecked&sort_type=desc"
        "&protocols=http%2Chttps"
    )

    @property
    def name(self) -> str:  # noqa: D401
        return "geonode"

    async def fetch_proxies(self) -> list[ProxyInfo]:
        """Fetch and parse proxies from GeoNode."""
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(self.URL)
                resp.raise_for_status()
                data = resp.json().get("data", [])
                proxies: list[ProxyInfo] = []
                for entry in data:
                    ip = entry.get("ip", "")
                    port_raw = entry.get("port", "")
                    if not ip or not port_raw:
                        continue
                    try:
                        port = int(port_raw)
                    except (ValueError, TypeError):
                        continue
                    protocols = entry.get("protocols", [])
                    protocol = self._pick_protocol(protocols)
                    country = entry.get("country", "")
                    proxies.append(
                        ProxyInfo(
                            ip=ip,
                            port=port,
                            protocol=protocol,
                            country=country,
                        )
                    )
                return proxies
        except Exception as exc:
            logger.warning("GeoNode fetch failed: %s", exc)
            return []

    @staticmethod
    def _pick_protocol(protocols: list[str]) -> ProxyProtocol:
        """Choose the best protocol from the list advertised by GeoNode."""
        for pref in ("https", "http", "socks5", "socks4"):
            if pref in protocols:
                return ProxyProtocol(pref)
        return ProxyProtocol.HTTP


class ProxyScrapeProvider(IProxyProvider):
    """Fetch proxies from the ProxyScrape API.

    Endpoint returns plain text with one ``ip:port`` per line.
    """

    URL = (
        "https://api.proxyscrape.com/v2/"
        "?request=displayproxies&protocol=http&timeout=5000&country=all"
    )

    @property
    def name(self) -> str:  # noqa: D401
        return "proxyscrape"

    async def fetch_proxies(self) -> list[ProxyInfo]:
        """Fetch and parse proxies from ProxyScrape."""
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(self.URL)
                resp.raise_for_status()
                return _parse_text_proxy_list(resp.text)
        except Exception as exc:
            logger.warning("ProxyScrape fetch failed: %s", exc)
            return []


class GitHubListProvider(IProxyProvider):
    """Fetch proxies from TheSpeedX's GitHub raw proxy list.

    Endpoint returns plain text with one ``ip:port`` per line.
    """

    URL = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"

    @property
    def name(self) -> str:  # noqa: D401
        return "github_list"

    async def fetch_proxies(self) -> list[ProxyInfo]:
        """Fetch and parse proxies from the GitHub list."""
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(self.URL)
                resp.raise_for_status()
                return _parse_text_proxy_list(resp.text)
        except Exception as exc:
            logger.warning("GitHub proxy list fetch failed: %s", exc)
            return []


def _parse_text_proxy_list(text: str) -> list[ProxyInfo]:
    """Parse a plain-text proxy list (``ip:port`` per line) into :class:`ProxyInfo` objects."""
    proxies: list[ProxyInfo] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":")
        if len(parts) != 2:
            continue
        ip, port_str = parts
        try:
            port = int(port_str)
        except ValueError:
            continue
        proxies.append(ProxyInfo(ip=ip, port=port))
    return proxies
