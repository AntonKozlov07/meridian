"""Tempo, key and energy: ReccoBeats by Spotify ID, then GetSongBPM as a fallback."""
from __future__ import annotations

import re

import httpx

from meridian.core.state import Track
from meridian.enrich.common import get_json

RECCO = "https://api.reccobeats.com/v1/audio-features"
GETSONGBPM = "https://api.getsongbpm.com/search/"
PITCH = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"]


def key_name(key: int | None, mode: int | None) -> str | None:
    if key is None or not 0 <= key <= 11 or mode not in (0, 1):
        return None
    return f"{PITCH[key]} {'major' if mode == 1 else 'minor'}"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def fetch_features(client: httpx.Client, track: Track, getsongbpm_key: str = "") -> dict | None:
    """{'bpm','key','energy','bpm_source','key_source'} with only the values found, or None. Raises Transient."""
    out: dict = {}
    data = get_json(client, RECCO, {"ids": track.id})
    rows = (data or {}).get("content") or []
    if rows:
        f = rows[0]
        if f.get("tempo"):
            out["bpm"], out["bpm_source"] = round(f["tempo"]), "ReccoBeats"
        k = key_name(f.get("key"), f.get("mode"))
        if k:
            out["key"], out["key_source"] = k, "ReccoBeats"
        if f.get("energy") is not None:
            out["energy"] = round(f["energy"] * 100)
    if getsongbpm_key and ("bpm" not in out or "key" not in out):
        out.update({k: v for k, v in _getsongbpm(client, track, getsongbpm_key).items() if k not in out})
    return out or None


def _getsongbpm(client: httpx.Client, track: Track, api_key: str) -> dict:
    artist = track.artists[0] if track.artists else track.artist
    data = get_json(client, GETSONGBPM, {"api_key": api_key, "type": "both", "lookup": f"song:{track.title} artist:{artist}"})
    hits = (data or {}).get("search")
    if not isinstance(hits, list):
        return {}
    hit = next((h for h in hits if _norm(h.get("title", "")) == _norm(track.title)), None)
    if not hit:
        return {}
    out: dict = {}
    try:
        if int(hit.get("tempo") or 0) > 0:
            out["bpm"], out["bpm_source"] = int(hit["tempo"]), "GetSongBPM"
    except (TypeError, ValueError):
        pass
    m = re.fullmatch(r"([A-G][♯♭#b]?)(m?)", (hit.get("key_of") or "").strip())
    if m:
        out["key"] = f"{m.group(1).replace('#', '♯')} {'minor' if m.group(2) else 'major'}"
        out["key_source"] = "GetSongBPM"
    return out
