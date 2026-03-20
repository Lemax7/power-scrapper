"""Tests for the SQLite response cache."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from power_scrapper.utils.cache import ResponseCache


@pytest.fixture()
def cache(tmp_path: Path) -> ResponseCache:
    """Create a cache in a temporary directory."""
    c = ResponseCache(db_path=tmp_path / "test_cache.db", ttl_hours=1)
    yield c
    c.close()


class TestResponseCache:
    def test_put_and_get(self, cache: ResponseCache) -> None:
        cache.put("https://example.com", "<html>hello</html>", 200)
        result = cache.get("https://example.com")
        assert result is not None
        body, status = result
        assert body == "<html>hello</html>"
        assert status == 200

    def test_miss_returns_none(self, cache: ResponseCache) -> None:
        assert cache.get("https://nonexistent.com") is None

    def test_expired_entry_returns_none(self, tmp_path: Path) -> None:
        # Create a cache with very short TTL.
        cache = ResponseCache(db_path=tmp_path / "expire_test.db", ttl_hours=0)
        cache.put("https://example.com", "body", 200)
        # Even with 0 TTL, the entry was just created so age ~0.
        # We need to manually set the fetched_at in the past.
        conn = cache._ensure_db()
        conn.execute(
            "UPDATE responses SET fetched_at = ? WHERE url = ?",
            (time.time() - 7200, "https://example.com"),
        )
        conn.commit()
        assert cache.get("https://example.com") is None
        cache.close()

    def test_overwrite_existing_entry(self, cache: ResponseCache) -> None:
        cache.put("https://example.com", "old body", 200)
        cache.put("https://example.com", "new body", 200)
        result = cache.get("https://example.com")
        assert result is not None
        body, _ = result
        assert body == "new body"

    def test_size(self, cache: ResponseCache) -> None:
        assert cache.size == 0
        cache.put("https://a.com", "a", 200)
        cache.put("https://b.com", "b", 200)
        assert cache.size == 2

    def test_clear_all(self, cache: ResponseCache) -> None:
        cache.put("https://a.com", "a", 200)
        cache.put("https://b.com", "b", 200)
        count = cache.clear_all()
        assert count == 2
        assert cache.size == 0

    def test_clear_expired(self, tmp_path: Path) -> None:
        cache = ResponseCache(db_path=tmp_path / "clear_test.db", ttl_hours=1)
        cache.put("https://fresh.com", "fresh", 200)
        cache.put("https://old.com", "old", 200)

        # Make one entry expired.
        conn = cache._ensure_db()
        conn.execute(
            "UPDATE responses SET fetched_at = ? WHERE url = ?",
            (time.time() - 7200, "https://old.com"),
        )
        conn.commit()

        count = cache.clear_expired()
        assert count == 1
        assert cache.size == 1
        assert cache.get("https://fresh.com") is not None
        assert cache.get("https://old.com") is None
        cache.close()

    def test_different_status_codes(self, cache: ResponseCache) -> None:
        cache.put("https://redirect.com", "moved", 301)
        result = cache.get("https://redirect.com")
        assert result is not None
        _, status = result
        assert status == 301

    def test_unicode_content(self, cache: ResponseCache) -> None:
        cache.put("https://ru.com", "Привет мир", 200)
        result = cache.get("https://ru.com")
        assert result is not None
        body, _ = result
        assert body == "Привет мир"

    def test_close_and_reopen(self, tmp_path: Path) -> None:
        db_path = tmp_path / "reopen_test.db"
        cache1 = ResponseCache(db_path=db_path, ttl_hours=24)
        cache1.put("https://persist.com", "data", 200)
        cache1.close()

        cache2 = ResponseCache(db_path=db_path, ttl_hours=24)
        result = cache2.get("https://persist.com")
        assert result is not None
        body, _ = result
        assert body == "data"
        cache2.close()
