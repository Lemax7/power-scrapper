# CLAUDE.md

## Project Purpose

`power_scrapper` is a universal news scraper replacing the Selenium-based scraper in `../news_analytics/scraping/`. Uses Patchright (stealth Playwright fork) for browser automation and SearXNG as a meta-search backend.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Easiest: auto-start SearXNG Docker + scrape (requires Docker Desktop running)
python -m power_scrapper -q "AI news" --docker-up

# Manual SearXNG
cd docker && docker compose up -d
python -m power_scrapper -q "AI news" --searxng-url http://localhost:8080
cd docker && docker compose down

# Browser-only (no Docker, requires: pip install patchright && patchright install chromium)
python -m power_scrapper -q "AI news" --pages 1
```

Output goes to `./output/` as Excel + JSON + CSV by default.

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
  --output-format {excel,json,csv,all}  Output format (default: all)
  --no-extract                Skip full article text extraction

Locale:
  -l, --language CODE         Search language (default: ru)
  -c, --country CODE          Search country (default: RU)

Other:
  --max-concurrent N          Max concurrent extractions (default: 10)
  --proxy                     Enable proxy rotation (planned)
  --config PATH               TOML config file path
  --debug                     Enable debug logging
```

## Usage Examples

```bash
# Russian news, last week, exact phrase
python -m power_scrapper -q "Мовиста Советников" -t w --strict-search --docker-up

# English news, 5 pages, JSON only
python -m power_scrapper -q "climate change" -p 5 -l en -c US --output-format json

# Only Google News tab, no text extraction (fast metadata-only scrape)
python -m power_scrapper -q "tech layoffs" --engines google-news --no-extract

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
output_formats = ["excel", "json", "csv"]
time_period = "w"
strict_search = false
expand_with_titles = false
max_titles_to_expand = 5
max_concurrent_extractions = 10
extract_articles = true
```

CLI args always override TOML values.

## Architecture

```
src/power_scrapper/
├── cli.py                  # CLI + TOML config + Docker lifecycle
├── config.py               # ScraperConfig, ArticleData dataclasses
├── errors.py               # Typed exception hierarchy
├── log.py                  # Structured logging setup
├── scraper.py              # Core async orchestrator (DI-based)
├── search/                 # Search backends (ISearchStrategy)
│   ├── base.py             # ABC + BrowserSearchStrategy (scrolling, browser mgmt)
│   ├── searxng.py          # SearXNG JSON API (primary)
│   ├── google_search.py    # Google Search via Patchright
│   ├── google_news.py      # Google News tab via Patchright
│   └── yandex.py           # Yandex Search via Patchright
├── extraction/             # Text extraction cascade
│   ├── base.py             # ITextExtractor ABC
│   ├── cascade.py          # Tries extractors in order (concurrent batch)
│   ├── trafilatura_ext.py  # Primary (fast, HTTP-only)
│   ├── newspaper_ext.py    # Fallback 1 (newspaper4k)
│   ├── readability_ext.py  # Fallback 2 (readability-lxml)
│   └── crawl4ai_ext.py     # Fallback 3 (clean markdown)
├── http/                   # Anti-detection HTTP tiers
│   ├── base.py             # IHttpClient, HttpResponse
│   ├── httpx_client.py     # Tier 1: standard HTTP/2
│   ├── curl_cffi_client.py # Tier 2: TLS fingerprint impersonation
│   ├── patchright_client.py# Tier 3: full stealth browser
│   └── tiered.py           # Auto-escalating per-domain
├── proxy/                  # Proxy rotation (optional)
│   ├── base.py             # ProxyInfo, IProxyProvider
│   ├── sources.py          # GeoNode, ProxyScrape, GitHub lists
│   └── manager.py          # Round-robin rotation + health tracking
├── output/                 # Output writers
│   ├── base.py             # IOutputWriter ABC
│   ├── excel.py            # Excel via pandas/openpyxl
│   ├── json_writer.py      # JSON (UTF-8, pretty-printed)
│   └── csv_writer.py       # CSV (UTF-8 with BOM)
└── utils/                  # Shared utilities
    ├── date_parser.py      # Russian + English date parsing
    ├── dedup.py            # Title + URL deduplication, relevance filter
    ├── text_cleaning.py    # Snippet date-prefix cleaning
    ├── punycode.py         # IDN domain decoding
    ├── small_media.py      # SmallMediaLoader from Excel
    └── url_builder.py      # URL construction + strict search
```

## Data Pipeline

```
Query
  → SearXNG JSON API  and/or  Patchright browser strategies
  → Raw articles (url, title, source, date, snippet)
  → Dedup (normalized titles + URLs)
  → Relevance filter (query term matching)
  → [Optional] Title expansion (re-search top titles)
  → [Optional] Small media (site:domain queries)
  → CascadeTextExtractor (trafilatura → newspaper4k → readability → crawl4ai)
  → Output: Excel + JSON + CSV
```

## Search Strategies

| Strategy | Backend | Bot Detection | When Used |
|----------|---------|--------------|-----------|
| SearXNG | JSON API via httpx | None needed | When `--searxng-url` or `--docker-up` |
| Google Search | Patchright browser | CAPTCHA + blocking phrases + URL redirect | Fallback when no SearXNG |
| Google News | Patchright browser | Same as Google Search | Fallback when no SearXNG |
| Yandex | Patchright browser | Yandex CAPTCHA selectors | Fallback when no SearXNG |

SearXNG aggregates Google + Yandex + Bing + DuckDuckGo + Google News in one query with zero bot detection risk.

## Anti-Detection

- **Page scrolling**: Browser strategies scroll pages (up to 2x) to load lazy content
- **Random delays**: 5-15s between page requests
- **Patchright**: Stealth Playwright fork that passes automation detection
- **TLS fingerprinting**: curl_cffi impersonates Chrome 124 for Cloudflare bypass
- **Tiered HTTP**: Auto-escalates httpx → curl_cffi → Patchright per domain
- **Bot detection handling**: Graceful skip on detection (doesn't crash)

## Development

```bash
# Test
pytest                        # all tests (343)
pytest -x --tb=short          # stop on first failure
pytest tests/test_search/ -v  # specific module

# Lint
ruff check .
ruff format .
```

## Key Design Patterns

- **SearXNG-first**: Prefer JSON API over browser scraping when available
- **Strategy pattern**: Pluggable search backends, text extractors, output writers, proxy providers
- **Dependency injection**: Scraper accepts optional overrides for all components
- **Cascade extraction**: Tries multiple extractors in priority order
- **Graceful degradation**: Bot detection skips strategy, extraction failures keep empty text
- **Russian + English**: Date parsing, bot detection phrases, snippet cleaning all bilingual
