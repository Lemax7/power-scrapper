"""HTTP client abstractions and implementations."""

from power_scrapper.http.base import HttpResponse, IHttpClient
from power_scrapper.http.httpx_client import HttpxClient

__all__ = [
    "HttpResponse",
    "HttpxClient",
    "IHttpClient",
]
