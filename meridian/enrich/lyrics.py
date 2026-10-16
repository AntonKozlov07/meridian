"""Synced lyrics from LRCLIB (https://lrclib.net)."""
from __future__ import annotations

import re

import httpx

from meridian.core.state import Track
from meridian.enrich.common import get_json

BASE = "https://lrclib.net/api"
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
    data = get_json(client, f"{BASE}/get", {**base, "album_name": track.album})
    if not data:
        data = get_json(client, f"{BASE}/get", base)  # album names often differ (deluxe, remaster)
    if not data:
        found = get_json(client, f"{BASE}/search", {"track_name": track.title, "artist_name": artist}) or []
        want = base["duration"]
        data = next((d for d in found if d.get("syncedLyrics") and abs((d.get("duration") or 0) - want) <= 3), None)
    if not data or data.get("instrumental") or not data.get("syncedLyrics"):
        return None
    lines = parse_lrc(data["syncedLyrics"])
    return {"lines": lines} if any(t for _, t in lines) else None
