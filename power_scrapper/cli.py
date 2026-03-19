"""CLI entry point for power_scrapper."""

from __future__ import annotations

import argparse
import asyncio

from power_scrapper.config import ScraperConfig
from power_scrapper.log import setup_logging
from power_scrapper.scraper import Scraper


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="power_scrapper",
        description="Universal news scraper with SearXNG, Google, and Yandex support",
    )
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument(
        "--pages", "-p", type=int, default=3, help="Max pages to scrape (default: 3)"
    )
    parser.add_argument(
        "--searxng-url", help="SearXNG instance URL (e.g. http://localhost:8080)"
    )
    parser.add_argument(
        "--output-dir", "-o", default="./output", help="Output directory (default: ./output)"
    )
    parser.add_argument(
        "--output-format",
        choices=["excel", "json", "csv", "all"],
        default="all",
        help="Output format (default: all)",
    )
    parser.add_argument(
        "--language", "-l", default="ru", help="Search language (default: ru)"
    )
    parser.add_argument(
        "--country", "-c", default="RU", help="Search country (default: RU)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the power_scrapper CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    formats = ["excel", "json", "csv"] if args.output_format == "all" else [args.output_format]

    config = ScraperConfig(
        query=args.query,
        max_pages=args.pages,
        language=args.language,
        country=args.country,
        debug=args.debug,
        searxng_url=args.searxng_url,
        output_dir=args.output_dir,
        output_formats=formats,
    )

    log = setup_logging(config.debug)
    log.info("Starting power_scrapper: query=%r, pages=%d", config.query, config.max_pages)

    scraper = Scraper(config)
    articles = asyncio.run(scraper.run())

    log.info("Done. %d articles scraped.", len(articles))


if __name__ == "__main__":
    main()
