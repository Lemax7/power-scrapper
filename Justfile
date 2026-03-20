# List available commands
default:
    @just --list

# --- Dev workflow ---

# Install/sync all dependencies (core + dev)
sync:
    uv sync

# Install with stealth extras (rnet, camoufox, nodriver, seleniumbase, crawl4ai)
sync-stealth:
    uv sync --extra stealth

# Run all tests
test *args:
    uv run pytest tests/ {{args}}

# Run linter
lint:
    uv run ruff check .

# Auto-format code
fmt:
    uv run ruff format .

# Lint + format
check: lint fmt

# Type check
typecheck:
    uv run mypy src/power_scrapper/

# Lock dependencies (regenerate uv.lock)
lock:
    uv lock

# --- Scraper CLI ---

# Run scraper (pass any CLI args): just scrape -q "AI news" --docker-up
scrape *args:
    uv run python -m power_scrapper {{args}}

# Quick scrape with Docker SearXNG auto-start
scrape-docker query *args:
    uv run python -m power_scrapper -q "{{query}}" --docker-up {{args}}

# Start SearXNG Docker container
docker-up:
    cd docker && docker compose up -d

# Stop SearXNG Docker container
docker-down:
    cd docker && docker compose down
