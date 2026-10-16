"""Synced lyrics from LRCLIB (https://lrclib.net)."""
from __future__ import annotations

import re
import threading
import time

import httpx

from meridian.core.state import Track
from meridian.enrich.common import Transient, get_json

BASE = "https://lrclib.net/api"
MIN_INTERVAL = 0.8  # seconds between requests: LRCLIB rate-limits (HTTP 429) when asked in bursts
RETRY_DELAY = 2.0  # wait before the single retry after a 429 or 5xx
_gate = threading.Lock()
_last = [0.0]


def _get(client: httpx.Client, url: str, params: dict):
    """One LRCLIB request at a time, spaced out, with a single retry when it is busy (429) or erroring (5xx).
    Holding the lock through the wait makes every other lyric lookup queue behind it instead of piling on."""
    with _gate:
        wait = MIN_INTERVAL - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            try:
                return get_json(client, url, params)
            except Transient:
                time.sleep(RETRY_DELAY)
                return get_json(client, url, params)
        finally:
            _last[0] = time.monotonic()
_TS = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
_OFFSET = re.compile(r"^\[offset:\s*([+-]?\d+)\s*\]", re.I | re.M)


def parse_lrc(text: str) -> list[list]:
    """LRC text to [[seconds, line], ...] sorted by time. Handles several stamps per line and [offset:]."""
    m = _OFFSET.search(text or "")
    offset = int(m.group(1)) / 1000 if m else 0.0
    out: list[list] = []
    for raw in (text or "").splitlines():
        stamps = list(_TS.finditer(raw))
        if not stamps:
            continue
        body = raw[stamps[-1].end():].strip()
        for s in stamps:
            frac = s.group(3) or "0"
            sec = int(s.group(1)) * 60 + int(s.group(2)) + int(frac) / 10 ** len(frac) - offset
            out.append([round(max(0.0, sec), 2), body])
    out.sort(key=lambda x: x[0])
    return out


def fetch_lyrics(client: httpx.Client, track: Track) -> dict | None:
    """{'lines': [[sec, text], ...]} or None when LRCLIB has no synced lyrics. Raises Transient."""
    artist = track.artists[0] if track.artists else track.artist
    base = {"track_name": track.title, "artist_name": artist, "duration": round(track.duration_ms / 1000)}
    data = _get(client, f"{BASE}/get", {**base, "album_name": track.album})
    if not data:
        data = _get(client, f"{BASE}/get", base)  # album names often differ (deluxe, remaster)
    if not data:
        found = _get(client, f"{BASE}/search", {"track_name": track.title, "artist_name": artist}) or []
        want = base["duration"]
        data = next((d for d in found if d.get("syncedLyrics") and abs((d.get("duration") or 0) - want) <= 3), None)
    if not data or data.get("instrumental") or not data.get("syncedLyrics"):
        return None
    lines = parse_lrc(data["syncedLyrics"])
    return {"lines": lines} if any(t for _, t in lines) else None
