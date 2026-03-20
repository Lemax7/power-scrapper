# CLAUDE.md

## Project Purpose

`power_scrapper` is a universal news scraper and LLM-ready text extraction tool. Uses multi-tier anti-detection HTTP (httpx → rnet → Camoufox → Patchright), SearXNG as a meta-search backend, and concurrent search strategies. Outputs clean markdown for LLM pipeline consumption (OpenClaw integration).

## Quick Start

```bash
# Install (core + dev deps via uv)
uv sync

# Install with stealth extras (rnet, camoufox, nodriver, seleniumbase, crawl4ai)
uv sync --extra stealth

# Easiest: auto-start SearXNG Docker + scrape (requires Docker Desktop running)
uv run python -m power_scrapper -q "AI news" --docker-up

# Manual SearXNG
cd docker && docker compose up -d
uv run python -m power_scrapper -q "AI news" --searxng-url http://localhost:8080
cd docker && docker compose down

# Browser-only (no Docker, requires: patchright install chromium)
uv run python -m power_scrapper -q "AI news" --pages 1

# LLM-ready markdown output
uv run python -m power_scrapper -q "AI news" --output-format markdown --max-chars 3000

# Or use Justfile shortcuts
just scrape -q "AI news" --docker-up
just scrape-docker "AI news"
```

Output goes to `./output/` as Excel + JSON + CSV + Markdown by default.

## CLI Reference

```
python -m power_scrapper [options]

Required:
  -q, --query TEXT            Search query

Search options:
  -p, --pages N               Max pages to scrape (default: 3)
  --searxng-url URL           SearXNG instance URL
  --docker-up                 Auto-start/stop SearXNG Docker container
  -t, --time-period {h,d,w,m} Time filter: hour/day/week/month
  --strict-search             Exact phrase matching (wraps query in quotes)
  --engines {google,google-news,yandex,all}  Browser engines (default: all)
  -e, --expand-titles         Re-search using top article titles
  --max-expand-titles N       Max titles for expansion (default: 5)
  --small-media-file PATH     Excel file with small media domains

Output options:
  -o, --output-dir DIR        Output directory (default: ./output)
  --output-format {excel,json,csv,markdown,all}  Output format (default: all)
  --no-extract                Skip full article text extraction
  --max-chars N               Max chars per article in markdown output (default: no limit)

Cache options:
  --no-cache                  Disable response cache
  --cache-ttl N               Cache TTL in hours (default: 24)
  --clear-cache               Clear expired cache entries before running

Locale:
  -l, --language CODE         Search language (default: ru)
  -c, --country CODE          Search country (default: RU)

Other:
  --max-concurrent N          Max concurrent extractions (default: 10)
  --proxy                     Enable proxy rotation
  --config PATH               TOML config file path
  --debug                     Enable debug logging
```

## Usage Examples

```bash
# Russian news, last week, exact phrase
python -m power_scrapper -q "Мовиста Советников" -t w --strict-search --docker-up

# English news, 5 pages, JSON only
python -m power_scrapper -q "climate change" -p 5 -l en -c US --output-format json

# LLM-ready markdown, truncated to 3000 chars per article
python -m power_scrapper -q "AI safety" --output-format markdown --max-chars 3000

# Only Google News tab, no text extraction (fast metadata-only scrape)
python -m power_scrapper -q "tech layoffs" --engines google-news --no-extract

# With proxy rotation enabled
python -m power_scrapper -q "AI news" --proxy --docker-up

# Second run uses cached responses (faster, fewer requests)
python -m power_scrapper -q "AI news" --docker-up --debug

# Title expansion to find related coverage
python -m power_scrapper -q "SpaceX launch" -e --max-expand-titles 3 --docker-up

# Small media search (low-visibility outlets from Excel list)
python -m power_scrapper -q "local politics" --small-media-file media_sources.xlsx --docker-up

# TOML config file (all settings in one place)
python -m power_scrapper -q "AI news" --config my_config.toml
```

## TOML Config File

Create `power_scrapper.toml` (auto-loaded if present, or specify with `--config`):

```toml
[scraper]
language = "ru"
country = "RU"
max_pages = 3
searxng_url = "http://localhost:8080"
output_dir = "./output"
output_formats = ["excel", "json", "csv", "markdown"]
time_period = "w"
strict_search = false
expand_with_titles = false
max_titles_to_expand = 5
max_concurrent_extractions = 10
extract_articles = true
cache_ttl_hours = 24
max_chars = 3000
```

CLI args always override TOML values.

## Architecture

```
src/power_scrapper/
├── cli.py                    # CLI + TOML config + Docker lifecycle + cache control
├── config.py                 # ScraperConfig, ArticleData dataclasses
├── errors.py                 # Typed exception hierarchy
├── log.py                    # Structured logging setup
├── scraper.py                # Core async orchestrator (DI-based, concurrent search)
├── search/                   # Search backends (ISearchStrategy)
│   ├── base.py               # ABC + BrowserSearchStrategy + AdaptiveRateLimiter
│   ├── searxng.py            # SearXNG JSON API (primary)
│   ├── google_search.py      # Google Search via Patchright
│   ├── google_news.py        # Google News tab via Patchright
│   ├── yandex.py             # Yandex Search via Patchright
│   ├── api_interceptor.py    # XHR/fetch API interception (structured JSON)
│   └── seleniumbase_strategy.py  # SeleniumBase CDP (CAPTCHA solving)
├── extraction/               # Text extraction cascade
│   ├── base.py               # ITextExtractor ABC
│   ├── cascade.py            # Tries extractors in order (pre-fetches HTML once)
│   ├── trafilatura_ext.py    # Primary (fast, HTTP-only)
│   ├── newspaper_ext.py      # Fallback 1 (newspaper4k)
│   ├── readability_ext.py    # Fallback 2 (readability-lxml)
│   ├── crawl4ai_ext.py       # Fallback 3 (v0.8.x, CSS selectors, shadow DOM)
│   └── patchright_ext.py     # Fallback 4 (full browser render)
├── http/                     # Multi-tier anti-detection HTTP
│   ├── base.py               # IHttpClient, HttpResponse
│   ├── httpx_client.py       # Tier 1: standard HTTP/2
│   ├── rnet_client.py        # Tier 2: Rust TLS fingerprint (Chrome 136+)
│   ├── curl_cffi_client.py   # Tier 2 fallback: TLS impersonation (legacy)
│   ├── camoufox_client.py    # Tier 2.5: Firefox anti-detect (C++ level)
│   ├── nodriver_client.py    # Alt: real Chrome via CDP (cookie extraction)
│   ├── patchright_client.py  # Tier 3: full stealth browser
│   └── tiered.py             # Auto-escalating per-domain + SQLite cache
├── proxy/                    # Proxy rotation (wired into scraper)
│   ├── base.py               # ProxyInfo, IProxyProvider
│   ├── sources.py            # GeoNode, ProxyScrape, GitHub lists
│   └── manager.py            # Round-robin rotation + health tracking
├── output/                   # Output writers
│   ├── base.py               # IOutputWriter ABC
│   ├── excel.py              # Excel via pandas/openpyxl
│   ├── json_writer.py        # JSON (UTF-8, pretty-printed)
│   ├── csv_writer.py         # CSV (UTF-8 with BOM)
│   └── markdown_writer.py    # Markdown (LLM-ready, metadata headers)
└── utils/                    # Shared utilities
    ├── cache.py              # SQLite response cache (URL → response, TTL)
    ├── rate_limiter.py        # Adaptive backoff + Poisson delays + AI Labyrinth
    ├── date_parser.py        # Russian + English date parsing
    ├── dedup.py              # Title + URL deduplication, relevance filter
    ├── text_cleaning.py      # Snippet date-prefix cleaning
    ├── punycode.py           # IDN domain decoding
    ├── small_media.py        # SmallMediaLoader from Excel
    └── url_builder.py        # URL construction + strict search
```

## Data Pipeline

```
Query
  → [Cache check: SQLite URL→response, TTL-based]
  → SearXNG JSON API  and/or  Browser strategies (concurrent via asyncio.gather)
  → Raw articles (url, title, source, date, snippet)
  → Dedup (normalized titles + URLs)
  → Relevance filter (query term matching)
  → [Optional] Title expansion (re-search top titles)
  → [Optional] Small media (site:domain queries)
  → CascadeTextExtractor (pre-fetches HTML once via TieredHttpClient)
    → trafilatura → newspaper4k → readability → crawl4ai → patchright
  → Output: Excel + JSON + CSV + Markdown (LLM-ready)
```

## HTTP Tier Escalation

```
Tier 1: httpx (fast HTTP/2)
  ↓ blocked? (403 / Cloudflare)
Tier 2: rnet (Rust TLS fingerprint, Chrome 136+)
  ↓ blocked?
Tier 2.5: Camoufox (Firefox anti-detect, C++ level fingerprint)
  ↓ blocked?
Tier 3: Patchright (full stealth Chromium)
  ↓ CAPTCHA?
Fallback: SeleniumBase CDP (sb.solve_captcha())

Per-domain memory: remembers which tier worked, starts there next time.
SQLite cache: avoids re-fetching same URLs across runs.
```

## Search Strategies

| Strategy | Backend | Bot Detection | When Used |
|----------|---------|--------------|-----------|
| SearXNG | JSON API via httpx | None needed | When `--searxng-url` or `--docker-up` |
| Google Search | Patchright browser | CAPTCHA + blocking phrases | Fallback when no SearXNG |
| Google News | Patchright browser | Same as Google Search | Fallback when no SearXNG |
| Yandex | Patchright browser | Yandex CAPTCHA selectors | Fallback when no SearXNG |
| API Interception | Patchright CDP route | N/A (intercepts JSON) | Advanced: captures API calls |
| SeleniumBase CDP | Real Chrome + CAPTCHA | Solves CAPTCHAs | Last resort for CAPTCHA sites |

All strategies run **concurrently** via `asyncio.gather()` with a semaphore (max 3 browsers).

## Anti-Detection

- **Adaptive rate limiting**: Poisson-distributed delays (human-like), exponential backoff on 429/403
- **AI Labyrinth detection**: Detects Cloudflare honeypot links, skips them
- **TLS fingerprinting**: rnet mimics Chrome 136 TLS handshake exactly
- **C++ fingerprinting**: Camoufox modifies Firefox fingerprints below JavaScript layer
- **Real Chrome**: NoDriver uses your actual Chrome installation (indistinguishable from human)
- **CAPTCHA solving**: SeleniumBase `solve_captcha()` for Cloudflare Turnstile, reCAPTCHA
- **Page scrolling**: Browser strategies scroll pages (up to 2x) to load lazy content
- **Tiered escalation**: Auto-escalates httpx → rnet → Camoufox → Patchright per domain
- **Per-domain memory**: Remembers which tier worked for each domain
- **Response caching**: SQLite cache avoids re-fetching, reducing detection risk
- **Proxy rotation**: Round-robin with health tracking, timezone matching

## Package Management

Uses **uv** for dependency management (not pip). Key commands:

```bash
uv sync                    # Install/sync all deps (core + dev)
uv sync --extra stealth    # Add stealth extras
uv lock                    # Regenerate uv.lock
uv add <package>           # Add a dependency
uv run <command>           # Run in project venv
```

Build backend: **hatchling** (not setuptools). Dev deps in `[dependency-groups]` (PEP 735).

## Development

```bash
# Test
uv run pytest tests/             # all tests (425)
uv run pytest tests/ -x --tb=short  # stop on first failure
uv run pytest tests/test_search/ -v  # specific module

# Lint
uv run ruff check .
uv run ruff format .

# Or use Justfile
just test                  # run all tests
just lint                  # ruff check
just fmt                   # ruff format
just check                 # lint + format
just typecheck             # mypy
```

## Key Design Patterns

- **SearXNG-first**: Prefer JSON API over browser scraping when available
- **Strategy pattern**: Pluggable search backends, text extractors, output writers, proxy providers, HTTP clients
- **Dependency injection**: Scraper accepts optional overrides for all components
- **Cascade extraction**: Tries multiple extractors in priority order with shared pre-fetched HTML
- **Concurrent search**: All strategies fire in parallel via asyncio.gather
- **Graceful degradation**: Bot detection skips strategy, extraction failures keep empty text
- **SQLite caching**: URL→response cache with TTL avoids redundant requests
- **Adaptive timing**: Poisson-distributed delays mimic human reading patterns
- **Russian + English**: Date parsing, bot detection phrases, snippet cleaning all bilingual
