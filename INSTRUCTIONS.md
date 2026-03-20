## Using `power-scrapper` as a package

### Install

```bash
# From GitHub (SSH)
pip install git+ssh://git@github.com/Lemax7/power-scrapper.git

# From GitHub (HTTPS — for CI or if SSH not configured)
pip install git+https://github.com/Lemax7/power-scrapper.git

# Pin to a branch
pip install git+ssh://git@github.com/Lemax7/power-scrapper.git@main

# From local path (if repos are side-by-side)
pip install -e /path/to/power_scrapper
```

### Add to your project's `pyproject.toml`

```toml
dependencies = [
    "power-scrapper @ git+ssh://git@github.com/Lemax7/power-scrapper.git@main",
]
```

### Usage

```python
import asyncio
from power_scrapper import scrape, Scraper, ScraperConfig, ArticleData

# --- Simple one-liner ---
articles = asyncio.run(scrape(
    "AI news",
    max_pages=2,
    searxng_url="http://localhost:8080",
))

# --- Full control ---
config = ScraperConfig(
    query="AI news",
    max_pages=3,
    language="en",
    country="US",
    searxng_url="http://localhost:8080",
    output_formats=["json"],
    time_period="w",
)
scraper = Scraper(config)
articles = asyncio.run(scraper.run())

# --- Inside an async function ---
async def get_news():
    articles = await scrape("AI news", max_pages=2)
    for a in articles:
        print(a.title, a.url, a.date)
        print(a.article_text[:200])
```

### `ScraperConfig` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | `str` | required | Search query |
| `max_pages` | `int` | `3` | Pages to scrape |
| `language` | `str` | `"ru"` | Search language |
| `country` | `str` | `"RU"` | Search country |
| `searxng_url` | `str \| None` | `None` | SearXNG instance URL |
| `output_dir` | `str` | `"./output"` | Where to write files |
| `output_formats` | `list[str]` | `["excel","json","csv"]` | Output formats |
| `time_period` | `str \| None` | `None` | `h`/`d`/`w`/`m` |
| `extract_articles` | `bool` | `True` | Extract full text |
| `strict_search` | `bool` | `False` | Exact phrase match |
| `max_concurrent_extractions` | `int` | `10` | Concurrency limit |
| `expand_with_titles` | `bool` | `False` | Re-search top titles |
| `only_strategies` | `list[str] \| None` | `None` | Filter: `"google_search"`, `"google_news"`, `"yandex"` |

### `ArticleData` fields

```python
article.url            # str
article.title          # str
article.source         # str (domain)
article.date           # datetime
article.body           # str (snippet)
article.article_text   # str (full extracted text)
article.source_type    # str: "searxng", "google_search", "google_news", "yandex"
article.page           # int
article.position       # int
```

### Notes

- SearXNG needs to be running separately (Docker or remote instance). Without it, the scraper falls back to browser-based Google/Yandex search via Patchright.
- If you only need metadata (no full text), pass `extract_articles=False` for a much faster run.
- The scraper writes output files by default. If you only want the returned `list[ArticleData]`, that works — files are a side effect.
