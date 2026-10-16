from unittest.mock import MagicMock

import spotipy

from meridian.api import Api
from meridian.config import Config
from meridian.sources.spotify import source as S
from meridian.sources.spotify.source import SpotifySource, parse_album, parse_artist, parse_playlist

IMG = [{"url": "https://img/a"}]


def pl(i, n=10, **kw):
    return {"id": f"p{i}", "uri": f"spotify:playlist:p{i}", "name": f"Playlist {i}", "images": IMG,
            "tracks": {"total": n}, "owner": {"display_name": "Anton"}, **kw}


def al(i):
    return {"id": f"a{i}", "uri": f"spotify:album:a{i}", "name": f"Album {i}", "images": IMG,
            "artists": [{"name": "Hollis Marr"}, {"name": "Ada"}]}


def ar(i):
    return {"id": f"r{i}", "uri": f"spotify:artist:r{i}", "name": f"Artist {i}", "images": []}


def make():
    sp = MagicMock()
    sp.current_user.return_value = {"id": "anton"}
    sp.current_user_saved_tracks.return_value = {"total": 1284}
    sp.current_user_playlists.return_value = {"items": [pl(1, 48), None, pl(2, 1)], "next": None}
    sp.current_user_saved_albums.return_value = {"items": [{"album": al(1)}], "next": None}
    sp.current_user_followed_artists.return_value = {"artists": {"items": [ar(1)], "cursors": {"after": None}}}
    return sp, SpotifySource(sp)


def test_parsers():
    p = parse_playlist(pl(1, 48))
    assert (p.kind, p.subtitle, p.art_url) == ("playlist", "Playlist · 48 songs", "https://img/a")
    assert parse_playlist(pl(2, 1)).subtitle == "Playlist · 1 song"
    assert parse_playlist({"id": "x", "uri": "u", "name": "n", "owner": {"display_name": "Sam"}}).subtitle == "Playlist · Sam"
    assert parse_playlist(pl(3, items={"total": 7}, tracks=None)).subtitle == "Playlist · 7 songs"  # renamed field
    assert parse_album(al(1)).subtitle == "Album · Hollis Marr, Ada"
    assert parse_artist(ar(1)).art_url is None and parse_artist(ar(1)).subtitle == "Artist"


def test_library_sections_and_liked_first():
    sp, src = make()
    lib = src.library()
    assert [i.name for i in lib.playlists] == ["Liked Songs", "Playlist 1", "Playlist 2"]  # null entry dropped
    assert lib.playlists[0].uri == "spotify:user:anton:collection" and lib.playlists[0].subtitle == "Playlist · 1,284 songs"
    assert [a.name for a in lib.albums] == ["Album 1"] and [a.name for a in lib.artists] == ["Artist 1"]
    assert lib.failed == []


def test_library_paginates_and_caps(monkeypatch):
    sp, src = make()
    monkeypatch.setattr(S, "LIBRARY_CAP", 100)
    pages = {0: {"items": [pl(i) for i in range(50)], "next": "x"}, 50: {"items": [pl(i) for i in range(50, 100)], "next": "x"}}
    sp.current_user_playlists.side_effect = lambda limit, offset: pages.get(offset, {"items": [pl(999)], "next": "x"})
    lib = src.library()
    assert len(lib.playlists) == 101  # 100 playlists + Liked Songs; the cap stopped the third page
    assert sp.current_user_playlists.call_count == 2


def test_library_followed_artists_use_cursor():
    sp, src = make()
    pages = [{"artists": {"items": [ar(1)], "cursors": {"after": "c1"}}}, {"artists": {"items": [ar(2)], "cursors": {"after": None}}}]
    sp.current_user_followed_artists.side_effect = pages
    assert [a.name for a in src.library().artists] == ["Artist 1", "Artist 2"]
    assert sp.current_user_followed_artists.call_args_list[1].kwargs["after"] == "c1"


def test_library_is_cached_until_forced():
    sp, src = make()
    src.library(); src.library()
    assert sp.current_user_playlists.call_count == 1
    src.library(force=True)
    assert sp.current_user_playlists.call_count == 2


def test_failing_section_is_reported_not_fatal():
    sp, src = make()
    sp.current_user_followed_artists.side_effect = spotipy.SpotifyException(403, -1, "x")
    lib = src.library()
    assert lib.failed == ["artists"] and lib.artists == [] and len(lib.playlists) == 3


def track(i, playable=True):
    return {"id": f"s{i}", "uri": f"spotify:track:s{i}", "name": f"Song {i}", "duration_ms": 1000, "is_playable": playable,
            "artists": [{"name": "A"}], "album": {"name": "Al", "images": IMG, "release_date": "2024"}}


def test_search_groups_and_filters():
    sp, src = make()
    sp.search.return_value = {"tracks": {"items": [track(1), track(2, playable=False), None]},
                              "playlists": {"items": [None, pl(1)]}, "albums": {"items": [al(1)]}, "artists": {"items": [ar(1)]}}
    r = src.search("  low tide ")
    sp.search.assert_called_with(q="low tide", type="track,playlist,album,artist", limit=5, market="from_token")
    assert [t.title for t in r.songs] == ["Song 1"]  # unplayable and null entries dropped
    assert [c.kind for c in r.collections] == ["playlist", "album", "artist"]


def test_empty_search_makes_no_request():
    sp, src = make()
    assert src.search("   ").songs == []
    sp.search.assert_not_called()


def test_play_uri_variants():
    sp, src = make()
    src.play_uri("spotify:track:s1", "track")
    sp.start_playback.assert_called_with(uris=["spotify:track:s1"])
    src.play_uri("spotify:album:a1", "album")
    sp.start_playback.assert_called_with(context_uri="spotify:album:a1")
    src.play_uri("spotify:user:anton:collection", "liked")
    sp.start_playback.assert_called_with(context_uri="spotify:user:anton:collection")


def test_api_wraps_results_and_errors():
    api = Api(Config()); sp, src = make(); api._source = src
    r = api.get_library()
    assert r["ok"] and r["data"]["playlists"][0]["name"] == "Liked Songs"
    sp.search.side_effect = spotipy.SpotifyException(429, -1, "x")
    assert api.search("x")["ok"] is False
    assert Api(Config()).search("x")["ok"] is False  # not connected
