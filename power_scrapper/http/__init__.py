"""HTTP client abstractions and implementations."""

from power_scrapper.http.base import HttpResponse, IHttpClient
from power_scrapper.http.curl_cffi_client import CurlCffiClient
from power_scrapper.http.httpx_client import HttpxClient
from power_scrapper.http.patchright_client import PatchrightClient
from power_scrapper.http.tiered import TieredHttpClient

__all__ = [
    "CurlCffiClient",
    "HttpResponse",
    "HttpxClient",
    "IHttpClient",
    "PatchrightClient",
    "TieredHttpClient",
]
