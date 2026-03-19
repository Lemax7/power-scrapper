"""Exception hierarchy for power_scrapper.

Every custom exception inherits from :class:`ScraperError` so callers can
catch a single base class when they don't need fine-grained handling.
"""


class ScraperError(Exception):
    """Base exception for all power_scrapper errors."""


# -- Configuration -----------------------------------------------------------

class ConfigError(ScraperError):
    """Invalid or missing configuration."""


# -- Search ------------------------------------------------------------------

class SearchError(ScraperError):
    """Failed to retrieve search results from any source."""


class SearXNGError(SearchError):
    """SearXNG-specific search failure (API unreachable, bad response, etc.)."""


class BotDetectedError(SearchError):
    """The target site flagged the request as bot traffic (CAPTCHA, 429, etc.)."""


class BrowserSearchError(SearchError):
    """Playwright-based search failed (timeout, selector not found, etc.)."""


# -- Extraction --------------------------------------------------------------

class ExtractionError(ScraperError):
    """Failed to extract article text from a page."""


# -- HTTP client -------------------------------------------------------------

class HttpClientError(ScraperError):
    """HTTP request failed across all client tiers."""


class AllTiersExhaustedError(HttpClientError):
    """Every HTTP client tier (httpx, curl_cffi, Playwright) was tried and failed."""


# -- Proxy -------------------------------------------------------------------

class ProxyError(ScraperError):
    """Proxy-related failure."""


class NoWorkingProxyError(ProxyError):
    """All available proxies have been exhausted or are non-functional."""


# -- Output ------------------------------------------------------------------

class OutputError(ScraperError):
    """Failed to write output (Excel, JSON, CSV, etc.)."""
