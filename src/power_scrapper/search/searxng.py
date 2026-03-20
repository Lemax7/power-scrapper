"""SearXNG JSON API search strategy."""

from __future__ import annotations

import json
import logging
from urllib.parse import quote_plus

from power_scrapper.config import ArticleData, ScraperConfig
from power_scrapper.errors import HttpClientError, SearXNGError
from power_scrapper.http.base import IHttpClient
from power_scrapper.search.base import ISearchStrategy
from power_scrapper.utils import DateParser
from power_scrapper.utils.punycode import extract_domain
from power_scrapper.utils.text_cleaning import clean_snippet

logger = logging.getLogger(__name__)

# Backward-compatible alias used by tests.
_extract_domain = extract_domain


class SearXNGStrategy(ISearchStrategy):
    """Query a SearXNG instance via its JSON API."""

    def __init__(self, base_url: str, http_client: IHttpClient) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http_client

    # ------------------------------------------------------------------
    # ISearchStrategy
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        config: ScraperConfig,
        *,
        max_pages: int = 3,
    ) -> list[ArticleData]:
        """Fetch news results from SearXNG for each page and return :class:`ArticleData` list."""
        all_results: list[ArticleData] = []

        for page in range(1, max_pages + 1):
            url = (
                f"{self._base_url}/search"
                f"?q={quote_plus(query)}"
                f"&format=json"
                f"&categories=news"
                f"&language={config.language}"
                f"&pageno={page}"
            )

            logger.debug("SearXNG request: %s", url)

            try:
                resp = await self._http.get(url)
            except HttpClientError as exc:
                raise SearXNGError(f"HTTP request to SearXNG failed: {exc}") from exc

            if resp.status_code != 200:
                raise SearXNGError(f"SearXNG returned HTTP {resp.status_code} for page {page}")

            try:
                data = json.loads(resp.text)
            except json.JSONDecodeError as exc:
                raise SearXNGError(f"SearXNG returned invalid JSON on page {page}: {exc}") from exc

            results = data.get("results", [])
            if not results:
                logger.info("SearXNG returned 0 results on page %d, stopping pagination", page)
                break

            for i, item in enumerate(results):
                article = ArticleData(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    source=_extract_domain(item.get("url", "")),
                    date=DateParser.parse_date(item.get("publishedDate", "")),
                    body=clean_snippet(item.get("content", "")),
                    source_type="searxng",
                    page=page,
                    position=i + 1,
                )
                all_results.append(article)

            logger.info(
                "SearXNG page %d: %d results (total so far: %d)",
                page,
                len(results),
                len(all_results),
            )

        # Calculate overall_position across all pages.
        for i, article in enumerate(all_results):
            article.overall_position = i + 1
        return all_results

    async def is_available(self) -> bool:
        """Check whether the SearXNG instance is reachable."""
        try:
            resp = await self._http.get(f"{self._base_url}/search?q=test&format=json")
            return resp.status_code == 200
        except (HttpClientError, Exception):  # noqa: BLE001
            return False

    @property
    def name(self) -> str:  # noqa: D401
        """Strategy name."""
        return "searxng"
