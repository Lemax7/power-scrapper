"""Proxy management: providers, rotation, and health tracking."""

from power_scrapper.proxy.base import IProxyProvider, ProxyInfo, ProxyProtocol
from power_scrapper.proxy.manager import ProxyManager
from power_scrapper.proxy.sources import (
    GeoNodeProvider,
    GitHubListProvider,
    ProxyScrapeProvider,
)

__all__ = [
    "GeoNodeProvider",
    "GitHubListProvider",
    "IProxyProvider",
    "ProxyInfo",
    "ProxyManager",
    "ProxyProtocol",
    "ProxyScrapeProvider",
]
