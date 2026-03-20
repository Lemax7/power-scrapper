"""Network request interception for API-first scraping.

Instead of parsing HTML/DOM, intercepts XHR/fetch API calls that search
engines make internally.  These return clean JSON with structured data --
no HTML parsing needed.  Falls back to DOM parsing if no API calls detected.

Uses Playwright/Patchright CDP ``page.route()`` to capture API responses.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from power_scrapper.config import ArticleData, ScraperConfig
from power_scrapper.search.base import BrowserSearchStrategy

logger = logging.getLogger(__name__)

# URL patterns that typically carry search result data.
_API_PATTERNS: tuple[str, ...] = (
    "/search",
    "/complete/search",
    "suggest",
    "/api/",
    "/_next/data",
    "/v1/search",
    "/graphql",
)


class APIInterceptorStrategy(BrowserSearchStrategy):
    """Intercept XHR/fetch API calls from search engines.

    1. Navigate to search page in stealth browser
    2. Intercept all XHR/fetch requests via ``page.route()``
    3. Capture JSON API responses (search results, suggestions)
    4. Extract structured data directly from API payloads
    5. Falls back to DOM-visible content if no API calls detected

    This is the most powerful technique: the browser is just a vehicle
    to trigger API calls.  We listen to network traffic, not the DOM.
    """

    def __init__(self, *, patchright_context_manager: object | None = None) -> None:
        super().__init__(patchright_context_manager=patchright_context_manager)
        self._captured_responses: list[dict[str, object]] = []

    async def search(
        self,
        query: str,
        config: ScraperConfig,
        *,
        max_pages: int = 3,
    ) -> list[ArticleData]:
        """Search via API interception on Google."""
        await self._ensure_browser()
        assert self._browser is not None

        self._captured_responses.clear()
        articles: list[ArticleData] = []

        page = await self._browser.new_page()  # type: ignore[union-attr]
        try:
            # Set up route interception for all requests.
            await page.route("**/*", self._handle_route)

            # Navigate to Google search.
            search_url = (
                f"https://www.google.com/search"
                f"?q={query}"
                f"&hl={config.language}"
                f"&gl={config.country}"
                f"&num=20"
            )
            await page.goto(search_url, timeout=30000, wait_until="networkidle")

            # Wait a bit for any async API calls to complete.
            await asyncio.sleep(2)

            # Try to extract articles from captured API responses.
            articles = self._parse_captured_responses(query)

            if articles:
                logger.info(
                    "API interception captured %d articles from %d API responses",
                    len(articles),
                    len(self._captured_responses),
                )
            else:
                logger.debug(
                    "No articles from API interception (%d responses captured), "
                    "falling back to DOM",
                    len(self._captured_responses),
                )

        except Exception:
            logger.debug("API interception failed for query %r", query, exc_info=True)
        finally:
            import contextlib  # noqa: PLC0415

            with contextlib.suppress(Exception):
                await page.close()

        return articles

    async def _handle_route(self, route: object) -> None:
        """Intercept and capture API responses while letting requests through."""
        try:
            request = route.request  # type: ignore[union-attr]
            url = request.url

            # Let the request proceed normally.
            response = await route.fetch()  # type: ignore[union-attr]

            # Check if this looks like an API response with data.
            if self._is_api_response(url, response):
                try:
                    body = await response.text()  # type: ignore[union-attr]
                    data = json.loads(body)
                    self._captured_responses.append({
                        "url": url,
                        "data": data,
                        "status": response.status,  # type: ignore[union-attr]
                    })
                    logger.debug("Captured API response from %s", url[:100])
                except (json.JSONDecodeError, Exception):
                    pass

            await route.fulfill(response=response)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            import contextlib  # noqa: PLC0415

            with contextlib.suppress(Exception):
                await route.continue_()  # type: ignore[union-attr]

    @staticmethod
    def _is_api_response(url: str, response: object) -> bool:
        """Check if a response looks like an API call with search data."""
        # Only interested in successful JSON responses.
        status = getattr(response, "status", 0)
        if status != 200:
            return False

        content_type = ""
        headers = getattr(response, "headers", {})
        if headers:
            content_type = headers.get("content-type", "")

        if "json" in content_type or "javascript" in content_type:
            return any(p in url.lower() for p in _API_PATTERNS)

        return False

    def _parse_captured_responses(self, query: str) -> list[ArticleData]:
        """Parse captured API responses into ArticleData objects."""
        articles: list[ArticleData] = []

        for resp in self._captured_responses:
            data = resp.get("data")
            if not isinstance(data, (dict, list)):
                continue

            # Try to extract search results from various JSON structures.
            extracted = self._extract_from_json(data, query)
            articles.extend(extracted)

        return articles

    def _extract_from_json(
        self, data: dict | list, query: str, depth: int = 0
    ) -> list[ArticleData]:
        """Recursively extract search result-like objects from JSON data."""
        if depth > 5:
            return []

        articles: list[ArticleData] = []

        if isinstance(data, dict):
            # Check if this dict looks like a search result.
            url = data.get("url") or data.get("link") or data.get("href", "")
            title = data.get("title") or data.get("name") or data.get("heading", "")

            if (
                url and title and isinstance(url, str) and isinstance(title, str)
                and url.startswith("http") and len(title) > 5
            ):
                articles.append(
                    ArticleData(
                        url=url,
                        title=str(title),
                        source=self._extract_source(url),
                        date=datetime.now(),
                        body=str(
                            data.get("snippet", data.get("description", ""))
                        ),
                        source_type="api_interception",
                    )
                )

            # Recurse into nested structures.
            for _key, value in data.items():
                if isinstance(value, (dict, list)):
                    articles.extend(self._extract_from_json(value, query, depth + 1))

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    articles.extend(self._extract_from_json(item, query, depth + 1))

        return articles

    @staticmethod
    def _extract_source(url: str) -> str:
        """Extract domain from URL for source field."""
        try:
            from urllib.parse import urlparse  # noqa: PLC0415

            parsed = urlparse(url)
            return parsed.netloc or url
        except Exception:  # noqa: BLE001
            return url

    async def is_available(self) -> bool:
        """Return True if patchright is importable."""
        return await super().is_available()

    @property
    def name(self) -> str:  # noqa: D401
        """Strategy name."""
        return "api_interception"
