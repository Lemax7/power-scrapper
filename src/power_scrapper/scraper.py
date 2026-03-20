"""Core async orchestrator -- wires search, dedup, and output into an end-to-end pipeline."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from power_scrapper.config import ArticleData, ScraperConfig
from power_scrapper.errors import BotDetectedError, SearchError
from power_scrapper.extraction.base import ITextExtractor
from power_scrapper.extraction.cascade import CascadeTextExtractor
from power_scrapper.http.base import IHttpClient
from power_scrapper.http.tiered import TieredHttpClient
from power_scrapper.log import setup_logging
from power_scrapper.output.base import IOutputWriter
from power_scrapper.output.csv_writer import CsvWriter
from power_scrapper.output.excel import ExcelWriter
from power_scrapper.output.json_writer import JsonWriter
from power_scrapper.output.markdown_writer import MarkdownWriter
from power_scrapper.proxy.manager import ProxyManager
from power_scrapper.search.base import ISearchStrategy
from power_scrapper.search.google_news import GoogleNewsStrategy
from power_scrapper.search.google_search import GoogleSearchStrategy
from power_scrapper.search.searxng import SearXNGStrategy
from power_scrapper.search.yandex import YandexSearchStrategy
from power_scrapper.utils.cache import ResponseCache
from power_scrapper.utils.dedup import deduplicate_articles, filter_relevant
from power_scrapper.utils.small_media import SmallMediaLoader
from power_scrapper.utils.url_builder import build_site_query

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Scraper:
    """Core async orchestrator.  DI-based -- accepts optional overrides for all components."""

    def __init__(
        self,
        config: ScraperConfig,
        *,
        search_strategies: list[ISearchStrategy] | None = None,
        output_writers: list[IOutputWriter] | None = None,
        text_extractor: ITextExtractor | None = None,
        http_client: IHttpClient | None = None,
        small_media_file: str | None = None,
    ) -> None:
        self.config = config
        self._http_client: IHttpClient | None = http_client
        self._search_strategies = search_strategies
        self._output_writers = output_writers
        self._text_extractor = text_extractor
        self._browser_strategies_to_close: list[ISearchStrategy] = []
        self._small_media_file = small_media_file
        self._cache: ResponseCache | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> list[ArticleData]:
        """Execute the full scraping pipeline.  Returns deduplicated articles."""
        run_logger = setup_logging(self.config.debug)

        # 1. Setup cache
        if self.config.use_cache:
            self._cache = ResponseCache(ttl_hours=self.config.cache_ttl_hours)

        # 1a. Setup proxy manager (if enabled)
        proxy_url: str | None = None
        if self.config.use_proxy:
            proxy_url = await self._setup_proxies(run_logger)

        # 2. Setup HTTP client (TieredHttpClient with auto-escalation + cache + proxy)
        if self._http_client is None:
            self._http_client = TieredHttpClient(
                cache=self._cache, proxy=proxy_url
            )

        extractor: ITextExtractor | None = None

        try:
            # 2. Setup search strategies (auto-detect SearXNG if url configured)
            strategies = self._search_strategies or await self._build_strategies()

            # 2a. Filter strategies if only_strategies is set.
            if self.config.only_strategies:
                allowed = set(self.config.only_strategies)
                strategies = [s for s in strategies if s.name in allowed]
                run_logger.info(
                    "Strategy filter active: using %s",
                    [s.name for s in strategies],
                )

            # 3. Search phase (concurrent — all strategies fire in parallel)
            all_articles: list[ArticleData] = await self._search_concurrent(
                strategies, run_logger
            )

            if not all_articles:
                run_logger.warning("No articles found from any strategy")
                return []

            # 4. Dedup + relevance filter
            articles = deduplicate_articles(all_articles)
            run_logger.info("After dedup: %d unique articles", len(articles))

            before = len(articles)
            articles = filter_relevant(articles, self.config.query)
            if len(articles) < before:
                run_logger.info(
                    "Relevance filter removed %d off-topic articles, %d remaining",
                    before - len(articles),
                    len(articles),
                )

            # 4a. Title expansion — re-search using top article titles
            if self.config.expand_with_titles and articles:
                articles = await self._expand_with_titles(articles, strategies)
                run_logger.info("After title expansion: %d articles", len(articles))

            # 4b. Small media search — search in low-visibility outlets
            if self._small_media_file:
                articles = await self._search_small_media(articles, strategies)
                run_logger.info("After small media search: %d articles", len(articles))

            # 5. Text extraction
            if self.config.extract_articles:
                extractor = self._text_extractor or CascadeTextExtractor(
                    http_client=self._http_client,
                )
                run_logger.info("Extracting article text with %s...", extractor.name)
                articles = await self._extract_texts(articles, extractor)
                run_logger.info(
                    "Extraction done: %d/%d articles have text",
                    sum(1 for a in articles if a.article_text),
                    len(articles),
                )

            # 6. Output
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            writers = self._output_writers or self._build_writers()

            stem = self._build_output_stem()
            for writer in writers:
                path = output_dir / f"{stem}{writer.extension}"
                written = writer.write(articles, path)
                run_logger.info("Wrote %s", written)

            return articles

        finally:
            # Close the text extractor (releases Patchright browser if used).
            if extractor is not None and hasattr(extractor, "close"):
                try:
                    await extractor.close()
                except Exception:  # noqa: BLE001
                    logger.debug("Failed to close text extractor")

            # Close browser-based strategies to release Patchright processes.
            for bs in self._browser_strategies_to_close:
                try:
                    if hasattr(bs, "close"):
                        await bs.close()
                except Exception:  # noqa: BLE001
                    logger.debug("Failed to close browser strategy %s", bs.name)
            self._browser_strategies_to_close.clear()

            if self._http_client:
                await self._http_client.close()

            if self._cache:
                self._cache.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _setup_proxies(self, run_logger: logging.Logger) -> str | None:
        """Fetch and test proxies, return a working proxy URL or None."""
        manager = ProxyManager()
        count = await manager.fetch_all()
        run_logger.info("Fetched %d proxies from all providers", count)

        if count == 0:
            run_logger.warning("No proxies available, proceeding without proxy")
            return None

        # Test proxies until we find a working one.
        for _ in range(min(count, 10)):
            proxy = manager.get_next()
            if proxy is None:
                break
            if await manager.test_proxy(proxy):
                run_logger.info("Using proxy: %s (%s)", proxy.url, proxy.country or "unknown")
                return proxy.url

        run_logger.warning("No working proxies found, proceeding without proxy")
        return None

    async def _search_concurrent(
        self,
        strategies: list[ISearchStrategy],
        run_logger: logging.Logger,
    ) -> list[ArticleData]:
        """Run all search strategies concurrently and merge results.

        Uses ``asyncio.gather()`` with a semaphore to limit concurrent
        browser instances (max 3).
        """
        semaphore = asyncio.Semaphore(3)

        async def _run_strategy(strategy: ISearchStrategy) -> list[ArticleData]:
            if not await strategy.is_available():
                run_logger.info("Strategy %s not available, skipping", strategy.name)
                return []
            async with semaphore:
                run_logger.info("Searching with %s...", strategy.name)
                try:
                    articles = await strategy.search(
                        self.config.query,
                        self.config,
                        max_pages=self.config.max_pages,
                    )
                    run_logger.info("%s returned %d articles", strategy.name, len(articles))
                    return articles
                except BotDetectedError as exc:
                    run_logger.warning(
                        "Bot detected on %s: %s — skipping strategy",
                        strategy.name,
                        exc,
                    )
                except SearchError as exc:
                    run_logger.warning("Strategy %s failed: %s", strategy.name, exc)
            return []

        results = await asyncio.gather(
            *[_run_strategy(s) for s in strategies],
            return_exceptions=True,
        )

        all_articles: list[ArticleData] = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
            elif isinstance(result, Exception):
                run_logger.warning("Strategy raised unexpected error: %s", result)

        return all_articles

    async def _build_strategies(self) -> list[ISearchStrategy]:
        """Build the default list of search strategies from config.

        SearXNG is preferred when configured.  Browser-based strategies
        (Google Search, Google News, Yandex) are added as fallbacks and
        are silently skipped when patchright is not installed.
        """
        strategies: list[ISearchStrategy] = []

        if self.config.searxng_url:
            assert self._http_client is not None
            strategies.append(SearXNGStrategy(self.config.searxng_url, self._http_client))

        # Browser-based fallbacks — each checks is_available() before use.
        browser_strategies: list[ISearchStrategy] = [
            GoogleSearchStrategy(),
            GoogleNewsStrategy(),
            YandexSearchStrategy(),
        ]
        for bs in browser_strategies:
            if await bs.is_available():
                strategies.append(bs)
                self._browser_strategies_to_close.append(bs)
            else:
                logger.debug("Browser strategy %s not available, skipping", bs.name)

        return strategies

    async def _extract_texts(
        self,
        articles: list[ArticleData],
        extractor: ITextExtractor,
    ) -> list[ArticleData]:
        """Run text extraction on articles using the cascade extractor."""
        if isinstance(extractor, CascadeTextExtractor):
            return await extractor.extract_batch(
                articles,
                max_concurrent=self.config.max_concurrent_extractions,
            )
        # For non-cascade extractors, do a simple sequential extraction
        for article in articles:
            if not article.article_text:
                article.article_text = await extractor.extract(article.url)
        return articles

    async def _expand_with_titles(
        self,
        articles: list[ArticleData],
        strategies: list[ISearchStrategy],
    ) -> list[ArticleData]:
        """Re-search with top article titles to find related coverage."""
        if not articles:
            return articles

        logger.info(
            "Expanding search with top %d article titles",
            self.config.max_titles_to_expand,
        )

        expansion_articles: list[ArticleData] = []
        titles = [
            a.title for a in articles[: self.config.max_titles_to_expand] if len(a.title) > 20
        ]

        for title in titles:
            for strategy in strategies:
                if await strategy.is_available():
                    try:
                        results = await strategy.search(
                            title,
                            self.config,
                            max_pages=1,
                        )
                        for r in results:
                            r.source_type = "google_search_expansion"
                        expansion_articles.extend(results)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Title expansion failed for %r: %s", title, exc)

        combined = articles + expansion_articles
        return deduplicate_articles(combined)

    async def _search_small_media(
        self,
        articles: list[ArticleData],
        strategies: list[ISearchStrategy],
    ) -> list[ArticleData]:
        """Search for the query within small media domains."""
        loader = SmallMediaLoader(self._small_media_file)
        domains = loader.domains

        if not domains:
            logger.info("No small media domains loaded, skipping")
            return articles

        logger.info("Searching %d small media domains", len(domains))
        media_articles: list[ArticleData] = []

        for domain in domains:
            site_query = build_site_query(self.config.query, domain)
            for strategy in strategies:
                if await strategy.is_available():
                    try:
                        results = await strategy.search(
                            site_query,
                            self.config,
                            max_pages=1,
                        )
                        for r in results:
                            r.source_type = "from_media_list"
                        media_articles.extend(results)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Small media search failed for %s: %s", domain, exc)
                    break  # Only use first available strategy per domain

        combined = articles + media_articles
        return deduplicate_articles(combined)

    def _build_output_stem(self) -> str:
        """Build a descriptive filename stem including query, time filter, and timestamp.

        Example: ``AI_news_w_3pages_20260320_143022``
        """
        query_part = self.config.query.replace(" ", "_")[:50]
        time_part = f"_{self.config.time_period}" if self.config.time_period else ""
        pages_part = f"_{self.config.max_pages}pages"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{query_part}{time_part}{pages_part}_{ts}"

    def _build_writers(self) -> list[IOutputWriter]:
        """Build output writers from the configured format list."""
        writers: list[IOutputWriter] = []
        for fmt in self.config.output_formats:
            if fmt == "excel":
                writers.append(ExcelWriter())
            elif fmt == "json":
                writers.append(JsonWriter())
            elif fmt == "csv":
                writers.append(CsvWriter())
            elif fmt == "markdown":
                writers.append(MarkdownWriter(max_chars=self.config.max_chars))
        return writers
