"""Lays the listening session out on a real clock: past, current, queued, context.

Offsets are milliseconds relative to the start of the current track (past tracks are
negative). Clock times are epoch milliseconds, computed from the wall clock at the
moment the playback state was read. The UI re-anchors them after a local seek or pause.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from meridian.core.state import Track

PAST, CURRENT, QUEUED, CONTEXT = "past", "cur", "mine", "next"


@dataclass
class TimelineBlock:
    kind: str  # past | cur | mine | next
    track: Track
    start_ms: int
    start_clock_ms: int


@dataclass
class Timeline:
    blocks: list[TimelineBlock] = field(default_factory=list)
    up_next: int = 0
    current_ends_ms: int = 0  # wall clock the current track ends
    queue_ends_ms: int = 0  # wall clock the last queued track ends


def build_timeline(
    current: Track,
    progress_ms: int,
    now_ms: int,
    past: list[Track],
    upcoming: list[tuple[Track, bool]],
    is_playing: bool = True,
) -> Timeline:
    """past is oldest first; upcoming is (track, user_queued) in play order.

    Unplayable tracks are skipped by Spotify, so they take no time and get no block.
    """
    origin = now_ms - progress_ms  # wall clock when the current track started (or would have)
    blocks: list[TimelineBlock] = []

    offset = 0
    placed: list[TimelineBlock] = []
    for track in reversed([t for t in past if t.is_playable]):
        offset -= track.duration_ms
        placed.append(TimelineBlock(PAST, track, offset, origin + offset))
    blocks.extend(reversed(placed))

    blocks.append(TimelineBlock(CURRENT, current, 0, origin))
    offset = current.duration_ms
    current_end = origin + offset

    queue_end = current_end
    up_next = 0
    for track, queued in upcoming:
        if not track.is_playable:
            continue
        blocks.append(TimelineBlock(QUEUED if queued else CONTEXT, track, offset, origin + offset))
        offset += track.duration_ms
        queue_end = origin + offset
        up_next += 1

    return Timeline(blocks=blocks, up_next=up_next, current_ends_ms=current_end, queue_ends_ms=queue_end)
