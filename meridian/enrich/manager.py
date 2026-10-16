"""Runs the enrichment sources in background threads and tells the UI as each one answers.

Nothing here can block or break playback: every job is isolated, failures are logged, and a source that
is down only leaves its own chip or panel empty.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import httpx

from meridian.config import Config
from meridian.core.state import Track
from meridian.enrich import art_color, credits, features, lastfm, lyrics
from meridian.enrich.cache import Cache
from meridian.enrich.common import Transient, user_agent

log = logging.getLogger(__name__)

KINDS = ("lyrics", "credits", "features", "lastfm", "art")
# (days kept when found, days kept when confirmed missing)
TTL = {"lyrics": (365, 3), "credits": (180, 7), "features": (180, 7), "lastfm": (1 / 24, 1 / 24), "art": (365, 30)}


class Enricher:
    def __init__(self, cfg: Config, cache: Cache, emit: Callable[[dict], None],
                 http: httpx.Client | None = None, lastfm_user: Callable[[], str | None] = lambda: None, workers: int = 4):
        self._cfg, self._cache, self._emit, self._lastfm_user = cfg, cache, emit, lastfm_user
        self._http = http or httpx.Client(timeout=12, follow_redirects=True,
                                          headers={"User-Agent": user_agent(cfg.musicbrainz_user_agent)})
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="enrich")
        self._inflight: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def request(self, track: Track, kinds: tuple[str, ...] = KINDS) -> None:
        for kind in kinds:
            if kind == "lastfm" and not self._cfg.lastfm_api_key:
                continue  # not configured: nothing to show, and nothing to pretend
            if kind == "art" and not track.art_url:
                continue
            key = (kind, self._key(kind, track))
            with self._lock:
                if key in self._inflight:
                    continue
                self._inflight.add(key)
            self._pool.submit(self._job, kind, track, key)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    # -- internals -------------------------------------------------------
    def _key(self, kind: str, track: Track) -> str:
        if kind == "art":
            return track.art_url or ""
        if kind == "lastfm":
            return f"{track.id}:{self._lastfm_user() or ''}"
        return track.id

    def _job(self, kind: str, track: Track, key: tuple[str, str]) -> None:
        try:
            found, value = self._cache.get(key[1], kind)
            error = False
            if not found:
                try:
                    value = self._fetch(kind, track)
                    hit, miss = TTL[kind]
                    self._cache.put(key[1], kind, self._store(kind, track, value), hit if value else miss)
                except Transient as e:
                    log.info("%s for %s unavailable right now: %s", kind, track.title, e)
                    value, error = None, True
            self._emit({"track_id": track.id, "kind": kind, "data": self._present(kind, value), "error": error})
        except Exception:
            log.exception("%s enrichment crashed for %s", kind, track.title)
            self._emit({"track_id": track.id, "kind": kind, "data": None, "error": True})
        finally:
            with self._lock:
                self._inflight.discard(key)

    def _fetch(self, kind: str, track: Track):
        if kind == "lyrics":
            return lyrics.fetch_lyrics(self._http, track)
        if kind == "credits":
            return credits.fetch_credits(self._http, track)
        if kind == "features":
            return features.fetch_features(self._http, track, self._cfg.getsongbpm_api_key)
        if kind == "lastfm":
            return lastfm.fetch_stats(self._http, track, self._cfg.lastfm_api_key, self._lastfm_user())
        return art_color.fetch_colors(self._http, track.art_url or "")

    @staticmethod
    def _present(kind: str, value):
        """What the page receives: the same shape whether it came from the network or the cache."""
        if kind == "lyrics" and value:
            return {"lines": value["lines"]}
        return value

    @staticmethod
    def _store(kind: str, track: Track, value):
        """Lyrics are stored with their track so cached lyrics can be searched by line later."""
        if kind == "lyrics" and value:
            return {"track": asdict(track), "lines": value["lines"]}
        return value

    def cached(self, kind: str, key: str):
        return self._cache.get(key, kind)
