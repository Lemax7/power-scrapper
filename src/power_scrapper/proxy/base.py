"""Proxy abstractions for power_scrapper."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ProxyProtocol(Enum):
    """Supported proxy protocols."""

    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


@dataclass
class ProxyInfo:
    """Represents a single proxy with metadata and health state."""

    ip: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    country: str = ""
    is_working: bool | None = None  # None = untested
    last_tested: datetime | None = None
    fail_count: int = 0

    @property
    def url(self) -> str:
        """Return the full proxy URL (e.g. ``http://1.2.3.4:8080``)."""
        return f"{self.protocol.value}://{self.ip}:{self.port}"


class IProxyProvider(ABC):
    """Abstract base for a source that supplies proxy lists."""

    @abstractmethod
    async def fetch_proxies(self) -> list[ProxyInfo]:
        """Fetch a list of proxies from this source."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier for this provider."""
