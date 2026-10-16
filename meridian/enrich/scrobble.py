"""When to scrobble. Last.fm's rule: the song is longer than 30s and was played for half its length or 4 minutes."""
from __future__ import annotations

from dataclasses import dataclass

from meridian.core.state import PlayerState, Track

MIN_LENGTH_MS = 30_000
MAX_NEEDED_MS = 240_000
MAX_STEP_MS = 12_000  # a progress jump bigger than this is a seek, not listening


@dataclass
class Event:
    kind: str  # "now_playing" | "scrobble"
    track: Track
    started_at: int  # epoch seconds


class ScrobbleTracker:
    def __init__(self) -> None:
        self._id: str | None = None
        self._last_ms = 0
        self._played = 0
        self._done = False
        self._started = 0

    def observe(self, s: PlayerState) -> list[Event]:
        if s.status != "ready" or not s.track:
            return []
        t, events = s.track, []
        restarted = self._id == t.id and self._last_ms > 20_000 and s.progress_ms < 8_000 and self._last_ms - s.progress_ms > 15_000
        if t.id != self._id or restarted:
            self._id, self._played, self._done = t.id, 0, False
            self._started = (s.fetched_at_ms - s.progress_ms) // 1000
            if t.duration_ms > MIN_LENGTH_MS:
                events.append(Event("now_playing", t, self._started))
        elif s.is_playing:
            step = s.progress_ms - self._last_ms
            if 0 < step <= MAX_STEP_MS:
                self._played += step
        self._last_ms = s.progress_ms
        need = min(t.duration_ms / 2, MAX_NEEDED_MS)
        if not self._done and t.duration_ms > MIN_LENGTH_MS and self._played >= need:
            self._done = True
            events.append(Event("scrobble", t, self._started))
        return events
