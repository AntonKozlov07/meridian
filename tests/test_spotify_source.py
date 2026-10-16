import spotipy
from unittest.mock import MagicMock

import pytest

from meridian.core.state import NO_DEVICE, READY
from meridian.sources.spotify.source import SpotifySource, parse_track

TRACK = {
    "id": "t1", "uri": "spotify:track:t1", "name": "Low Tide Arithmetic", "duration_ms": 252000,
    "artists": [{"name": "Hollis Marr"}, {"name": "Ada Pruett"}], "track_number": 3,
    "external_ids": {"isrc": "GB1234567890"}, "is_playable": True,
    "album": {"name": "Field Recordings Vol. II", "release_date": "2024-05-03", "total_tracks": 11,
              "images": [{"url": "https://img/big"}, {"url": "https://img/small"}]},
}
PLAYBACK = {
    "is_playing": True, "progress_ms": 74000, "shuffle_state": True, "repeat_state": "context",
    "item": TRACK, "context": {"type": "playlist", "uri": "spotify:playlist:p1"},
    "device": {"id": "d1", "name": "Laptop", "type": "Computer", "is_active": True, "volume_percent": 72},
}
DEVICES = {"devices": [
    {"id": "d1", "name": "Laptop", "type": "Computer", "is_active": True, "volume_percent": 72},
    {"id": "d2", "name": "Speaker", "type": "Speaker", "is_active": False, "is_restricted": True},
]}


def make(playback=PLAYBACK):
    sp = MagicMock()
    sp.current_playback.return_value = playback
    sp.devices.return_value = DEVICES
    sp.playlist.return_value = {"name": "Late Hours"}
    sp.current_user_saved_tracks_contains.return_value = [True]
    return sp, SpotifySource(sp)


def test_parse_track():
    t = parse_track(TRACK)
    assert (t.title, t.artist, t.year, t.art_url) == ("Low Tide Arithmetic", "Hollis Marr, Ada Pruett", 2024, "https://img/big")
    assert (t.track_number, t.album_tracks, t.isrc) == (3, 11, "GB1234567890")


def test_parse_track_without_date_or_art():
    t = parse_track({"id": "x", "name": "n", "artists": [], "album": {"name": "a"}})
    assert t.year is None and t.art_url is None


def test_poll_ready():
    sp, src = make()
    s = src.poll()
    assert s.status == READY and s.is_playing and s.shuffle and s.repeat == "context"
    assert s.progress_ms == 74000 and s.volume == 0.72
    assert s.context_name == "Late Hours" and s.liked is True
    assert [d.name for d in s.devices] == ["Laptop", "Speaker"] and s.devices[1].is_restricted
    assert s.to_dict()["track"]["title"] == "Low Tide Arithmetic"


def test_context_and_like_are_cached():
    sp, src = make()
    src.poll(); src.poll()
    assert sp.playlist.call_count == 1 and sp.current_user_saved_tracks_contains.call_count == 1


def test_poll_no_active_device():
    sp, src = make(playback=None)
    s = src.poll()
    assert s.status == NO_DEVICE and s.track is None and len(s.devices) == 2


def test_controls_map_to_spotify_calls():
    sp, src = make()
    src.play(); src.pause(); src.next(); src.previous()
    src.seek(-5); src.set_volume(150); src.set_shuffle(True); src.set_repeat("track"); src.transfer("d2")
    sp.start_playback.assert_called_once(); sp.pause_playback.assert_called_once()
    sp.next_track.assert_called_once(); sp.previous_track.assert_called_once()
    sp.seek_track.assert_called_with(0); sp.volume.assert_called_with(100)
    sp.shuffle.assert_called_with(True); sp.repeat.assert_called_with("track")
    sp.transfer_playback.assert_called_with("d2", force_play=True)


def test_bad_repeat_mode():
    _, src = make()
    with pytest.raises(ValueError):
        src.set_repeat("forever")


def test_save_and_unsave_updates_cache():
    sp, src = make()
    src.set_saved("t1", False)
    sp.current_user_saved_tracks_delete.assert_called_with(["t1"])
    assert src.poll().liked is False


def item(i, secs=100, playable=True):
    return {"id": f"q{i}", "uri": f"spotify:track:q{i}", "name": f"Q{i}", "duration_ms": secs * 1000,
            "artists": [{"name": "A"}], "album": {"name": "Al"}, "is_playable": playable}


def test_poll_builds_timeline_from_history_and_queue():
    sp, src = make()
    sp.current_user_recently_played.return_value = {"items": [
        {"track": TRACK}, {"track": item(1)}, {"track": item(2)}, {"track": item(1)}]}  # current + dup dropped
    sp.queue.return_value = {"queue": [item(3), item(4)]}
    tl = src.poll().timeline
    assert [b.kind for b in tl.blocks] == ["past", "past", "cur", "next", "next"]
    assert [b.track.id for b in tl.blocks[:2]] == ["q2", "q1"]  # oldest first
    assert tl.up_next == 2


def test_queued_from_meridian_is_marked_then_cleared_when_played():
    sp, src = make()
    sp.queue.return_value = {"queue": [item(3), item(4)]}
    src.add_to_queue("spotify:track:q3")
    sp.add_to_queue.assert_called_with("spotify:track:q3")
    assert [b.kind for b in src.poll().timeline.blocks if b.kind != "cur"] == ["mine", "next"]
    # q3 starts playing: it is the current track and no longer counts as queued
    pb = dict(PLAYBACK, item=item(3))
    sp.current_playback.return_value = pb
    sp.queue.return_value = {"queue": [item(4)]}
    assert [b.kind for b in src.poll().timeline.blocks if b.kind not in ("cur", "past")] == ["next"]


def test_history_and_queue_not_reread_every_poll():
    sp, src = make()
    src.poll(); src.poll(); src.poll()
    assert sp.current_user_recently_played.call_count == 1 and sp.queue.call_count == 1


def test_skip_invalidates_and_rereads():
    sp, src = make()
    src.poll(); src.next(); src.poll()
    assert sp.queue.call_count == 2 and sp.current_user_recently_played.call_count == 2


def test_failed_queue_read_keeps_last_known():
    import spotipy
    sp, src = make()
    sp.queue.return_value = {"queue": [item(3)]}
    src.poll()
    sp.queue.side_effect = spotipy.SpotifyException(500, -1, "x")
    src.next()
    assert src.poll().timeline.up_next == 1


def test_play_track_prefers_context_then_falls_back():
    import spotipy
    sp, src = make(); src.poll()
    src.play_track("spotify:track:z")
    sp.start_playback.assert_called_with(device_id="d1", context_uri="spotify:playlist:p1", offset={"uri": "spotify:track:z"})
    sp.start_playback.reset_mock()
    sp.start_playback.side_effect = [spotipy.SpotifyException(404, -1, "not in context"), None]
    src.play_track("spotify:track:z")
    sp.start_playback.assert_called_with(device_id="d1", uris=["spotify:track:z"])


def test_jump_ahead_skips_n_times_or_replays_when_far(monkeypatch):
    monkeypatch.setattr("meridian.sources.spotify.source.time.sleep", lambda s: None)
    sp, src = make(); src.poll()
    src.jump_ahead(3, "spotify:track:z")
    assert sp.next_track.call_count == 3
    sp.next_track.reset_mock()
    src.jump_ahead(12, "spotify:track:z")
    assert sp.next_track.call_count == 0 and sp.start_playback.called


def test_play_targets_the_active_device_explicitly():
    sp, src = make(); src.poll()
    src.play_uri("spotify:track:s1", "track")
    sp.start_playback.assert_called_with(device_id="d1", uris=["spotify:track:s1"])
    src.play_at("spotify:track:s1", 5000); sp.start_playback.assert_called_with(device_id="d1", uris=["spotify:track:s1"], position_ms=5000)
    src.play(); sp.start_playback.assert_called_with(device_id="d1")


def test_idle_phone_is_woken_instead_of_failing():
    """The phone dropped out as active: Spotify answers NO_ACTIVE_DEVICE. Meridian retries on the last device it used."""
    sp, src = make(); src.poll()  # d1 (Laptop) active and remembered
    sp.current_playback.return_value = None; src.poll()  # now nothing is active
    sp.devices.return_value = {"devices": [{"id": "phone", "name": "Phone", "type": "Smartphone", "is_active": False},
                                           {"id": "d1", "name": "Laptop", "type": "Computer", "is_active": False}]}
    gone = spotipy.SpotifyException(404, -1, "Device not found", reason="NO_ACTIVE_DEVICE")
    sp.start_playback.side_effect = [gone, None]
    src.play_uri("spotify:track:s1", "track")
    assert [c.kwargs["device_id"] for c in sp.start_playback.call_args_list] == ["d1", "d1"]  # last-used device, not "whatever"


def test_other_404s_are_not_mistaken_for_a_missing_device():
    sp, src = make(); src.poll()
    sp.start_playback.side_effect = spotipy.SpotifyException(404, -1, "Track not in context", reason="")
    with pytest.raises(spotipy.SpotifyException):
        src._start(uris=["x"])
    assert sp.start_playback.call_count == 1 and sp.devices.call_count == 1  # the one device list is poll()'s


def test_no_device_to_wake_raises_a_clear_error():
    sp, src = make(playback=None); src.poll()
    sp.devices.return_value = {"devices": []}
    sp.start_playback.side_effect = spotipy.SpotifyException(404, -1, "x", reason="NO_ACTIVE_DEVICE")
    with pytest.raises(spotipy.SpotifyException):
        src.play_uri("spotify:track:s1", "track")


def _playing(uri, name="Phone"):
    return {"is_playing": True, "progress_ms": 0, "item": {**TRACK, "uri": uri}, "device": {"id": "d1", "name": name, "type": "Smartphone", "is_active": True}}


def test_verified_play_makes_no_second_attempt(monkeypatch):
    monkeypatch.setattr("meridian.sources.spotify.source.VERIFY_PLAYBACK", True)
    sp, src = make(); src.poll()
    sp.current_playback.return_value = _playing("spotify:track:s1")
    src.play_uri("spotify:track:s1", "track")
    assert sp.start_playback.call_count == 1


def test_play_that_did_not_take_is_retried_once(monkeypatch):
    """Spotify accepted the command but nothing is playing (the phone dropped it). Retry on the same device, once."""
    monkeypatch.setattr("meridian.sources.spotify.source.VERIFY_PLAYBACK", True)
    sp, src = make(); src.poll()
    sp.current_playback.return_value = {"is_playing": False, "item": TRACK, "device": {"id": "d1", "name": "Phone"}}
    src.play_uri("spotify:track:s1", "track")
    assert sp.start_playback.call_count == 2
    assert all(c.kwargs["device_id"] == "d1" for c in sp.start_playback.call_args_list)


def test_wrong_song_playing_is_retried(monkeypatch):
    monkeypatch.setattr("meridian.sources.spotify.source.VERIFY_PLAYBACK", True)
    sp, src = make(); src.poll()
    sp.current_playback.return_value = _playing("spotify:track:something-else")
    src.play_uri("spotify:track:s1", "track")
    assert sp.start_playback.call_count == 2


def test_unknown_spotify_errors_say_what_spotify_said():
    from meridian.api import friendly_error
    msg = friendly_error(spotipy.SpotifyException(403, -1, "Restriction violated", reason="UNKNOWN"))
    assert "403" in msg and "UNKNOWN" in msg
