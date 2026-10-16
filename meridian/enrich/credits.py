"""Credits from MusicBrainz: ISRC to recording, then performer, writer, producer and engineer relationships.

MusicBrainz allows 1 request/second and requires a descriptive User-Agent.
"""
from __future__ import annotations

import threading
import time

import httpx

from meridian.core.state import Track
from meridian.enrich.common import get_json

BASE = "https://musicbrainz.org/ws/2"
_gate = threading.Lock()
_last = [0.0]
MIN_INTERVAL = 1.1  # seconds between requests, across all threads

WRITER_TYPES = ("writer", "composer", "lyricist")
# (label, relationship types). Order is display order.
GROUPS = [
    ("Performed by", ("vocal", "instrument", "performer", "conductor", "orchestra")),
    ("Written by", WRITER_TYPES),
    ("Arranged by", ("arranger",)),
    ("Produced by", ("producer",)),
    ("Mixed by", ("mix",)),
    ("Engineered by", ("recording", "engineer")),
    ("Mastered by", ("mastering",)),
]
MAX_PER_GROUP = 8


def _throttled_get(client: httpx.Client, url: str, params: dict):
    with _gate:
        wait = MIN_INTERVAL - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            return get_json(client, url, params)
        finally:
            _last[0] = time.monotonic()


def _add(group: dict[str, list[str]], name: str, roles: list[str]) -> None:
    have = group.setdefault(name, [])
    for r in roles:
        if r and r not in have:
            have.append(r)


def build_groups(recording: dict) -> list[list]:
    """MusicBrainz recording JSON (with artist-rels and work-level-rels) to [[label, [[name, role|None], ...]], ...]."""
    buckets: dict[str, dict[str, list[str]]] = {label: {} for label, _ in GROUPS}
    credit = [c.get("artist", {}).get("name") for c in recording.get("artist-credit", []) if isinstance(c, dict)]
    for rel in recording.get("relations", []):
        kind = rel.get("type")
        if rel.get("artist"):
            for label, types in GROUPS:
                if kind in types:
                    roles = list(rel.get("attributes") or [])
                    if kind == "vocal" and not roles:
                        roles = ["vocals"]
                    _add(buckets[label], rel["artist"]["name"], roles)
        elif rel.get("work"):  # writers hang off the work, not the recording
            for wr in rel["work"].get("relations", []):
                if wr.get("artist") and wr.get("type") in WRITER_TYPES:
                    _add(buckets["Written by"], wr["artist"]["name"], [])
    if not any(buckets.values()):
        return []
    for name in credit:  # the credited artists lead the performer list
        if name and name not in buckets["Performed by"]:
            buckets["Performed by"] = {name: [], **buckets["Performed by"]}
    out = []
    for label, _ in GROUPS:
        people = buckets[label]
        if people:
            out.append([label, [[n, ", ".join(r) if r else None] for n, r in list(people.items())[:MAX_PER_GROUP]]])
    return out


def fetch_credits(client: httpx.Client, track: Track) -> dict | None:
    """{'groups': [...]} or None (no ISRC, unknown to MusicBrainz, or no relationships). Raises Transient."""
    if not track.isrc:
        return None
    found = _throttled_get(client, f"{BASE}/isrc/{track.isrc}", {"fmt": "json"})
    recs = (found or {}).get("recordings") or []
    if not recs:
        return None
    want = track.duration_ms
    rec = min(recs, key=lambda r: abs((r.get("length") or want) - want))
    full = _throttled_get(client, f"{BASE}/recording/{rec['id']}", {
        "inc": "artist-credits+artist-rels+work-rels+work-level-rels", "fmt": "json"})
    groups = build_groups(full or {})
    return {"groups": groups} if groups else None
