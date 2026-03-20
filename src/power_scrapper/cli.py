"""CLI entry point for power_scrapper."""

from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any

from power_scrapper.config import ScraperConfig
from power_scrapper.log import setup_logging
from power_scrapper.scraper import Scraper

# ---------------------------------------------------------------------------
# TOML config
# ---------------------------------------------------------------------------

_DEFAULT_TOML = "power_scrapper.toml"


def load_toml_config(path: str | Path) -> dict[str, Any]:
    """Load TOML configuration file and return the [scraper] section.

    Returns an empty dict if the file does not exist.
    """
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("rb") as f:
        data = tomllib.load(f)
    return data.get("scraper", {})


def _merge_config(toml_cfg: dict[str, Any], cli_ns: argparse.Namespace) -> dict[str, Any]:
    """Merge TOML defaults with CLI overrides.  CLI args take precedence.

    Only CLI values that were explicitly provided (not ``None`` and not the
    parser default for store_true flags) overwrite TOML values.
    """
    merged: dict[str, Any] = dict(toml_cfg)

    # Map CLI namespace attrs -> config keys  (same names where possible)
    cli_map: dict[str, str] = {
        "query": "query",
        "pages": "max_pages",
        "searxng_url": "searxng_url",
        "output_dir": "output_dir",
        "language": "language",
        "country": "country",
        "debug": "debug",
        "strict_search": "strict_search",
        "expand_titles": "expand_with_titles",
        "max_expand_titles": "max_titles_to_expand",
        "proxy": "use_proxy",
        "time_period": "time_period",
        "max_concurrent": "max_concurrent_extractions",
    }

    for cli_attr, cfg_key in cli_map.items():
        val = getattr(cli_ns, cli_attr, None)
        if val is not None:
            merged[cfg_key] = val

    return merged


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="power_scrapper",
        description="Universal news scraper with SearXNG, Google, and Yandex support",
    )

    # Required
    parser.add_argument("--query", "-q", required=True, help="Search query")

    # Search options
    parser.add_argument(
        "--pages", "-p", type=int, default=3, help="Max pages to scrape (default: 3)"
    )
    parser.add_argument("--searxng-url", help="SearXNG instance URL (e.g. http://localhost:8080)")
    parser.add_argument(
        "--time-period",
        "-t",
        choices=["h", "d", "w", "m"],
        default=None,
        help="Time period filter: h=hour, d=day, w=week, m=month",
    )

    # Output options
    parser.add_argument(
        "--output-dir", "-o", default="./output", help="Output directory (default: ./output)"
    )
    parser.add_argument(
        "--output-format",
        choices=["excel", "json", "csv", "markdown", "all"],
        default="all",
        help="Output format (default: all)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Max characters per article text in markdown output (default: no limit)",
    )

    # Locale
    parser.add_argument("--language", "-l", default="ru", help="Search language (default: ru)")
    parser.add_argument("--country", "-c", default="RU", help="Search country (default: RU)")

    # Engine selection (browser-based fallback strategies)
    parser.add_argument(
        "--engines",
        nargs="*",
        choices=["google", "google-news", "yandex", "all"],
        default=["all"],
        help="Browser engines to use (default: all). SearXNG is always used when configured.",
    )

    # Extraction control
    parser.add_argument(
        "--no-extract",
        action="store_true",
        default=False,
        help="Skip article text extraction",
    )

    # Strict search
    parser.add_argument(
        "--strict-search",
        action="store_true",
        default=None,
        help="Enable strict (exact phrase) search — wraps query in quotes",
    )

    # Title expansion
    parser.add_argument(
        "--expand-titles",
        "-e",
        action="store_true",
        default=None,
        help="Enable title expansion (re-search with top article titles)",
    )
    parser.add_argument(
        "--max-expand-titles",
        type=int,
        default=None,
        help="Max titles to use for expansion (default: 5)",
    )

    # Small media
    parser.add_argument(
        "--small-media-file",
        default=None,
        help="Path to Excel file with media sources for small media search",
    )

    # Proxy
    parser.add_argument(
        "--proxy",
        action="store_true",
        default=None,
        help="Enable proxy usage (planned, not yet active)",
    )

    # Concurrency
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help="Max concurrent article extractions (default: 10)",
    )

    # Cache control
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Disable response cache",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=None,
        help="Cache TTL in hours (default: 24)",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        default=False,
        help="Clear expired cache entries before running",
    )

    # Config file
    parser.add_argument(
        "--config",
        default=None,
        help="Path to TOML config file (default: power_scrapper.toml if present)",
    )

    # Docker lifecycle
    parser.add_argument(
        "--docker-up",
        action="store_true",
        default=False,
        help="Auto-start SearXNG Docker container before scraping and stop it after",
    )

    # Debug
    parser.add_argument("--debug", action="store_true", default=None, help="Enable debug logging")

    return parser


# ---------------------------------------------------------------------------
# Docker lifecycle
# ---------------------------------------------------------------------------

_DOCKER_COMPOSE_DIR = Path(__file__).resolve().parent.parent.parent / "docker"


def _docker_compose_up(log: logging.Logger) -> bool:
    """Start SearXNG via docker compose. Returns True on success."""
    compose_file = _DOCKER_COMPOSE_DIR / "docker-compose.yml"
    if not compose_file.exists():
        log.error("docker-compose.yml not found at %s", compose_file)
        return False

    log.info("Starting SearXNG container...")
    result = subprocess.run(
        ["docker", "compose", "up", "-d"],
        cwd=_DOCKER_COMPOSE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.error("Failed to start SearXNG: %s", result.stderr.strip())
        return False

    # Wait for SearXNG to be ready (up to 30s)
    import httpx

    for i in range(30):
        try:
            resp = httpx.get("http://localhost:8080/healthz", timeout=2)
            if resp.status_code == 200:
                log.info("SearXNG is ready on http://localhost:8080")
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)

    log.warning("SearXNG started but health check timed out — proceeding anyway")
    return True


def _docker_compose_down(log: logging.Logger) -> None:
    """Stop SearXNG via docker compose."""
    log.info("Stopping SearXNG container...")
    subprocess.run(
        ["docker", "compose", "down"],
        cwd=_DOCKER_COMPOSE_DIR,
        capture_output=True,
        text=True,
    )


def main(argv: list[str] | None = None) -> None:
    """Run the power_scrapper CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load TOML config (explicit --config or default file)
    toml_path = args.config or _DEFAULT_TOML
    toml_cfg = load_toml_config(toml_path)

    # Merge TOML + CLI
    merged = _merge_config(toml_cfg, args)

    # Handle output formats
    output_format = args.output_format
    if output_format == "all":
        formats = merged.get("output_formats", ["excel", "json", "csv", "markdown"])
    else:
        formats = [output_format]

    # Resolve engine selection to internal strategy names.
    engine_map: dict[str, str] = {
        "google": "google_search",
        "google-news": "google_news",
        "yandex": "yandex",
    }
    engines = merged.get("engines", args.engines) or ["all"]
    if "all" in engines:
        only_strategies: list[str] | None = None
    else:
        only_strategies = [engine_map[e] for e in engines if e in engine_map]

    config = ScraperConfig(
        query=merged.get("query", args.query),
        max_pages=merged.get("max_pages", 3),
        language=merged.get("language", "ru"),
        country=merged.get("country", "RU"),
        debug=merged.get("debug", False),
        searxng_url=merged.get("searxng_url"),
        output_dir=merged.get("output_dir", "./output"),
        output_formats=formats,
        use_proxy=merged.get("use_proxy", False),
        expand_with_titles=merged.get("expand_with_titles", False),
        max_titles_to_expand=merged.get("max_titles_to_expand", 5),
        time_period=merged.get("time_period"),
        max_concurrent_extractions=merged.get("max_concurrent_extractions", 10),
        strict_search=merged.get("strict_search", False),
        extract_articles=not args.no_extract,
        only_strategies=only_strategies,
        use_cache=not args.no_cache,
        cache_ttl_hours=args.cache_ttl or merged.get("cache_ttl_hours", 24),
        max_chars=args.max_chars or merged.get("max_chars"),
    )

    log = setup_logging(config.debug)
    log.info("Starting power_scrapper: query=%r, pages=%d", config.query, config.max_pages)

    # Handle cache clearing
    if args.clear_cache:
        from power_scrapper.utils.cache import ResponseCache  # noqa: PLC0415

        cache = ResponseCache(ttl_hours=config.cache_ttl_hours)
        cache.clear_expired()
        cache.close()

    # Auto-start SearXNG if requested
    docker_started = False
    if args.docker_up:
        docker_started = _docker_compose_up(log)
        if docker_started and not config.searxng_url:
            config.searxng_url = "http://localhost:8080"

    try:
        scraper = Scraper(config, small_media_file=args.small_media_file)
        articles = asyncio.run(scraper.run())
        log.info("Done. %d articles scraped.", len(articles))
    finally:
        if docker_started and args.docker_up:
            _docker_compose_down(log)


if __name__ == "__main__":
    main()
