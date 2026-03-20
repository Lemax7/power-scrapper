"""SQLite-based HTTP response cache for avoiding redundant requests."""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "power_scrapper"
_DEFAULT_TTL_HOURS = 24


class ResponseCache:
    """SQLite cache for HTTP responses.

    Stores URL -> response body mappings with a configurable TTL.
    Thread-safe via SQLite's built-in locking.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Defaults to
        ``~/.cache/power_scrapper/responses.db``.
    ttl_hours:
        Time-to-live in hours.  Entries older than this are considered
        expired.  Default: 24.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        ttl_hours: int = _DEFAULT_TTL_HOURS,
    ) -> None:
        self._db_path = db_path or (_DEFAULT_CACHE_DIR / "responses.db")
        self._ttl_hours = ttl_hours
        self._conn: sqlite3.Connection | None = None

    def _ensure_db(self) -> sqlite3.Connection:
        """Lazily create the database and table."""
        if self._conn is not None:
            return self._conn

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                url TEXT PRIMARY KEY,
                response_body TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                fetched_at REAL NOT NULL,
                ttl_hours INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()
        return self._conn

    def get(self, url: str) -> tuple[str, int] | None:
        """Return cached ``(response_body, status_code)`` or *None* if miss/expired."""
        conn = self._ensure_db()
        cursor = conn.execute(
            "SELECT response_body, status_code, fetched_at, ttl_hours FROM responses WHERE url = ?",
            (url,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        body, status_code, fetched_at, ttl_hours = row
        age_hours = (time.time() - fetched_at) / 3600
        if age_hours > ttl_hours:
            # Expired -- delete and return miss.
            conn.execute("DELETE FROM responses WHERE url = ?", (url,))
            conn.commit()
            return None

        logger.debug("Cache HIT for %s (age=%.1fh)", url, age_hours)
        return body, status_code

    def put(self, url: str, response_body: str, status_code: int) -> None:
        """Store a response in the cache."""
        conn = self._ensure_db()
        conn.execute(
            """
            INSERT OR REPLACE INTO responses
            (url, response_body, status_code, fetched_at, ttl_hours)
            VALUES (?, ?, ?, ?, ?)
            """,
            (url, response_body, status_code, time.time(), self._ttl_hours),
        )
        conn.commit()
        logger.debug("Cache PUT for %s (status=%d)", url, status_code)

    def clear_expired(self) -> int:
        """Delete all expired entries.  Returns count of deleted rows."""
        conn = self._ensure_db()
        now = time.time()
        cursor = conn.execute(
            "DELETE FROM responses WHERE (? - fetched_at) / 3600.0 > ttl_hours",
            (now,),
        )
        conn.commit()
        count = cursor.rowcount
        if count:
            logger.info("Cleared %d expired cache entries", count)
        return count

    def clear_all(self) -> int:
        """Delete all cache entries.  Returns count of deleted rows."""
        conn = self._ensure_db()
        cursor = conn.execute("DELETE FROM responses")
        conn.commit()
        count = cursor.rowcount
        logger.info("Cleared all %d cache entries", count)
        return count

    @property
    def size(self) -> int:
        """Number of entries currently in the cache."""
        conn = self._ensure_db()
        cursor = conn.execute("SELECT COUNT(*) FROM responses")
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
