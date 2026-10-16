from meridian.core.state import Track
from meridian.core.timeline import CONTEXT, CURRENT, PAST, QUEUED, build_timeline


def tr(i, secs, playable=True):
    return Track(id=f"t{i}", uri=f"spotify:track:t{i}", title=f"T{i}", artist="A", album="Al", year=2024,
                 duration_ms=secs * 1000, art_url=None, is_playable=playable)


NOW = 1_000_000_000_000  # epoch ms


def test_layout_offsets_and_clock_times():
    tl = build_timeline(tr(0, 200), progress_ms=60_000, now_ms=NOW,
                        past=[tr(1, 100), tr(2, 150)],
                        upcoming=[(tr(3, 180), True), (tr(4, 120), False)])
    kinds = [b.kind for b in tl.blocks]
    assert kinds == [PAST, PAST, CURRENT, QUEUED, CONTEXT]
    starts = [b.start_ms for b in tl.blocks]
    assert starts == [-250_000, -150_000, 0, 200_000, 380_000]
    origin = NOW - 60_000  # current track began a minute ago
    assert [b.start_clock_ms for b in tl.blocks] == [origin + s for s in starts]
    assert tl.current_ends_ms == origin + 200_000  # 140s from now
    assert tl.queue_ends_ms == origin + 500_000
    assert tl.up_next == 2


def test_past_is_oldest_first_and_contiguous_with_current():
    tl = build_timeline(tr(0, 100), 0, NOW, past=[tr(1, 40), tr(2, 60)], upcoming=[])
    assert [b.track.id for b in tl.blocks] == ["t1", "t2", "t0"]
    assert tl.blocks[1].start_ms + 60_000 == 0  # last past block ends where current begins


def test_empty_queue():
    tl = build_timeline(tr(0, 100), 40_000, NOW, past=[], upcoming=[])
    assert tl.up_next == 0 and tl.queue_ends_ms == tl.current_ends_ms == NOW + 60_000
    assert [b.kind for b in tl.blocks] == [CURRENT]


def test_unplayable_tracks_take_no_time_and_get_no_block():
    tl = build_timeline(tr(0, 100), 0, NOW, past=[], upcoming=[(tr(1, 50, playable=False), False), (tr(2, 70), False)])
    assert [b.track.id for b in tl.blocks] == ["t0", "t2"]
    assert tl.blocks[1].start_ms == 100_000 and tl.up_next == 1


def test_paused_clock_is_anchored_to_now_minus_progress():
    a = build_timeline(tr(0, 100), 30_000, NOW, [], [(tr(1, 10), False)])
    b = build_timeline(tr(0, 100), 30_000, NOW + 5_000, [], [(tr(1, 10), False)])
    assert b.queue_ends_ms - a.queue_ends_ms == 5_000
