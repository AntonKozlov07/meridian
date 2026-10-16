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
