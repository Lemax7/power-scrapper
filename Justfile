# List available commands
default:
    @just --list

# --- Dev workflow ---

# Run all tests
test *args:
    uv run pytest tests/ {{args}}

# Run linter
lint:
    ruff check .

# Auto-format code
fmt:
    ruff format .

# Lint + format
check: lint fmt

# Type check
typecheck:
    uv run mypy power_scrapper/

# Install in dev mode
install:
    pip install -e ".[dev]"

# Build distribution
build:
    uv run python -m build

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
