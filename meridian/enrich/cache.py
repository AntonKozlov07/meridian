"""SQLite cache for enrichment, keyed by Spotify track ID (or album art URL).

A confirmed miss is cached too (value null) so we do not ask again on every play, but
for a shorter time than a hit. Transient failures are never written here.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DAY = 86400


def default_path() -> Path:
    p = Path.home() / ".meridian"
    p.mkdir(exist_ok=True)
    return p / "cache.db"


class Cache:
    def __init__(self, path: str | Path | None = None):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path or default_path()), check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT NOT NULL, kind TEXT NOT NULL, value TEXT, "
            "expires_at REAL NOT NULL, PRIMARY KEY (key, kind))"
        )
        self._db.commit()

    def get(self, key: str, kind: str) -> tuple[bool, Any]:
        """(True, value) when a fresh entry exists. value is None for a cached miss."""
        with self._lock:
            row = self._db.execute("SELECT value, expires_at FROM cache WHERE key=? AND kind=?", (key, kind)).fetchone()
        if not row or row[1] < time.time():
            return False, None
        return True, json.loads(row[0]) if row[0] is not None else None

    def put(self, key: str, kind: str, value: Any, ttl_days: float) -> None:
        raw = None if value is None else json.dumps(value, ensure_ascii=False)
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)", (key, kind, raw, time.time() + ttl_days * DAY))
            self._db.commit()

    def search_lyrics(self, query: str, limit: int = 5) -> list[dict]:
        """Lines matching `query` across lyrics already cached. Returns [{track, line: [seconds, text]}]."""
        q = query.strip().lower()
        if len(q) < 3:
            return []
        with self._lock:
            rows = self._db.execute(
                "SELECT value FROM cache WHERE kind='lyrics' AND value IS NOT NULL AND expires_at>? "
                "AND lower(value) LIKE ? ESCAPE '\\'",
                (time.time(), "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"),
            ).fetchall()
        hits = []
        for (raw,) in rows:
            v = json.loads(raw)
            line = next((ln for ln in v.get("lines", []) if q in ln[1].lower()), None)
            if line:
                hits.append({"track": v["track"], "line": line})
            if len(hits) >= limit:
                break
        return hits
