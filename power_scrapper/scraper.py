"""Core async orchestrator -- wires search, dedup, and output into an end-to-end pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from power_scrapper.config import ArticleData, ScraperConfig
from power_scrapper.errors import SearchError
from power_scrapper.http.httpx_client import HttpxClient
from power_scrapper.log import setup_logging
from power_scrapper.output.base import IOutputWriter
from power_scrapper.output.csv_writer import CsvWriter
from power_scrapper.output.excel import ExcelWriter
from power_scrapper.output.json_writer import JsonWriter
from power_scrapper.search.base import ISearchStrategy
from power_scrapper.search.searxng import SearXNGStrategy
from power_scrapper.utils.dedup import deduplicate_articles

if TYPE_CHECKING:
    pass  # Future: ITextExtractor will be imported here

logger = logging.getLogger(__name__)


class Scraper:
    """Core async orchestrator.  DI-based -- accepts optional overrides for all components."""

    def __init__(
        self,
        config: ScraperConfig,
        *,
        search_strategies: list[ISearchStrategy] | None = None,
        output_writers: list[IOutputWriter] | None = None,
    ) -> None:
        self.config = config
        self._http_client: HttpxClient | None = None
        self._search_strategies = search_strategies
        self._output_writers = output_writers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> list[ArticleData]:
        """Execute the full scraping pipeline.  Returns deduplicated articles."""
        run_logger = setup_logging(self.config.debug)

        # 1. Setup HTTP client
        self._http_client = HttpxClient()

        try:
            # 2. Setup search strategies (auto-detect SearXNG if url configured)
            strategies = self._search_strategies or await self._build_strategies()

            # 3. Search phase
            all_articles: list[ArticleData] = []
            for strategy in strategies:
                if await strategy.is_available():
                    run_logger.info("Searching with %s...", strategy.name)
                    try:
                        articles = await strategy.search(
                            self.config.query,
                            self.config,
                            max_pages=self.config.max_pages,
                        )
                        run_logger.info(
                            "%s returned %d articles", strategy.name, len(articles)
                        )
                        all_articles.extend(articles)
                    except SearchError as exc:
                        run_logger.warning("Strategy %s failed: %s", strategy.name, exc)
                else:
                    run_logger.info("Strategy %s not available, skipping", strategy.name)

            if not all_articles:
                run_logger.warning("No articles found from any strategy")
                return []

            # 4. Dedup
            articles = deduplicate_articles(all_articles)
            run_logger.info("After dedup: %d unique articles", len(articles))

            # 5. Text extraction (placeholder -- will be wired in Phase 3)
            # if self.config.extract_articles and self._text_extractor:
            #     articles = await self._extract_texts(articles)

            # 6. Output
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            writers = self._output_writers or self._build_writers()

            stem = self.config.query.replace(" ", "_")[:50]
            for writer in writers:
                path = output_dir / f"{stem}{writer.extension}"
                written = writer.write(articles, path)
                run_logger.info("Wrote %s", written)

            return articles

        finally:
            if self._http_client:
                await self._http_client.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_strategies(self) -> list[ISearchStrategy]:
        """Build the default list of search strategies from config."""
        strategies: list[ISearchStrategy] = []
        if self.config.searxng_url:
            assert self._http_client is not None
            strategies.append(SearXNGStrategy(self.config.searxng_url, self._http_client))
        # Browser strategies will be added in Phase 4
        return strategies

    def _build_writers(self) -> list[IOutputWriter]:
        """Build output writers from the configured format list."""
        writer_map: dict[str, type[IOutputWriter]] = {
            "excel": ExcelWriter,
            "json": JsonWriter,
            "csv": CsvWriter,
        }
        return [writer_map[fmt]() for fmt in self.config.output_formats if fmt in writer_map]
