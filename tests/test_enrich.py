import io
import json
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image

from meridian.config import Config
from meridian.core.state import PlayerState, Track
from meridian.enrich import art_color, credits, features, lastfm, lyrics
from meridian.enrich.cache import Cache
from meridian.enrich.common import Transient
from meridian.enrich.manager import Enricher
from meridian.enrich.scrobble import ScrobbleTracker

FIX = Path(__file__).parent / "fixtures"


def track(**kw):
    d = dict(id="3BQHpFgAp4l80e1XslIjNI", uri="spotify:track:3BQ", title="Yesterday", artist="The Beatles", album="Help!",
             year=1965, duration_ms=125_000, art_url="https://img/a", isrc="GBAYE0601498", artists=["The Beatles"])
    d.update(kw)
    return Track(**d)


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---- LRC + lyrics -----------------------------------------------------------

def test_parse_lrc():
    text = "[ar:Someone]\n[00:12.50]First line\n[00:05.00]Early\n[01:02.5][02:03.25]Chorus\n[00:20.00]\n[offset:+500]"
    out = lyrics.parse_lrc(text)
    assert out[0] == [4.5, "Early"] and out[1] == [12.0, "First line"]
    assert [t for t, x in out if x == "Chorus"] == [62.0, 122.75]
    assert [20 - 0.5, ""] in out  # empty instrumental lines keep their time
    assert lyrics.parse_lrc("") == [] and lyrics.parse_lrc("no stamps here") == []


def test_lyrics_found_on_first_try():
    calls = []
    def h(req):
        calls.append(req.url.path); q = dict(req.url.params)
        assert q["track_name"] == "Yesterday" and q["artist_name"] == "The Beatles" and q["duration"] == "125"
        return httpx.Response(200, json={"syncedLyrics": "[00:01.00]Yesterday\n[00:05.00]All my troubles"})
    r = lyrics.fetch_lyrics(client(h), track())
    assert r == {"lines": [[1.0, "Yesterday"], [5.0, "All my troubles"]]} and calls == ["/api/get"]


def test_lyrics_fall_back_without_album_then_to_search():
    seen = []
    def h(req):
        seen.append((req.url.path, "album_name" in req.url.params))
        if req.url.path == "/api/search":
            return httpx.Response(200, json=[{"syncedLyrics": None, "duration": 125}, {"syncedLyrics": "[00:02.00]Hi", "duration": 300},
                                             {"syncedLyrics": "[00:03.00]Right one", "duration": 126}])
        return httpx.Response(404, json={})
    r = lyrics.fetch_lyrics(client(h), track())
    assert r == {"lines": [[3.0, "Right one"]]}  # skipped the unsynced one and the wrong-length one
    assert seen == [("/api/get", True), ("/api/get", False), ("/api/search", False)]


@pytest.mark.parametrize("payload", [{"instrumental": True, "syncedLyrics": None}, {"plainLyrics": "words", "syncedLyrics": None}])
def test_lyrics_miss(payload):
    assert lyrics.fetch_lyrics(client(lambda r: httpx.Response(200, json=payload)), track()) is None


@pytest.mark.parametrize("status", [429, 503])
def test_lyrics_rate_limit_is_transient_not_a_miss(status):
    with pytest.raises(Transient):
        lyrics.fetch_lyrics(client(lambda r: httpx.Response(status)), track())


def test_network_error_is_transient():
    def boom(req): raise httpx.ConnectError("down")
    with pytest.raises(Transient):
        lyrics.fetch_lyrics(client(boom), track())


# ---- features ---------------------------------------------------------------

RECCO = {"content": [{"id": "x", "tempo": 96.524, "key": 5, "mode": 1, "energy": 0.179}]}


def test_key_names():
    assert features.key_name(6, 0) == "F♯ minor" and features.key_name(3, 1) == "E♭ major"
    assert features.key_name(-1, 1) is None and features.key_name(None, None) is None


def test_features_from_reccobeats():
    def h(req):
        assert req.url.params["ids"] == "3BQHpFgAp4l80e1XslIjNI"
        return httpx.Response(200, json=RECCO)
    assert features.fetch_features(client(h), track()) == {"bpm": 97, "bpm_source": "ReccoBeats", "key": "F major",
                                                           "key_source": "ReccoBeats", "energy": 18}


def test_getsongbpm_fills_gaps_only_with_a_key():
    def h(req):
        if "reccobeats" in req.url.host:
            return httpx.Response(200, json={"content": []})
        assert req.url.params["api_key"] == "K"
        return httpx.Response(200, json={"search": [{"title": "Something else", "tempo": "1"},
                                                    {"title": "Yesterday", "tempo": "96", "key_of": "F♯m"}]})
    r = features.fetch_features(client(h), track(), "K")
    assert r == {"bpm": 96, "bpm_source": "GetSongBPM", "key": "F♯ minor", "key_source": "GetSongBPM"}  # no energy invented
    assert features.fetch_features(client(h), track(), "") is None  # no key, no fallback, nothing found


def test_getsongbpm_no_result_shape_is_a_miss():
    def h(req):
        return httpx.Response(200, json={"content": []} if "recco" in req.url.host else {"search": {"error": "no result"}})
    assert features.fetch_features(client(h), track(), "K") is None


# ---- credits (real MusicBrainz response for Yellow Submarine) ----------------

def test_build_groups_from_real_musicbrainz_json():
    groups = dict((g[0], g[1]) for g in credits.build_groups(json.loads((FIX / "mb_recording.json").read_text(encoding="utf-8"))))
    perf = dict((n, r) for n, r in groups["Performed by"])
    assert list(perf)[0] == "The Beatles"  # credited artist leads
    assert perf["George Harrison"] and "tambourine" in perf["George Harrison"] and "background vocals" in perf["George Harrison"]
    assert perf["Ringo Starr"].startswith("drums") or "lead vocals" in perf["Ringo Starr"]
    assert [n for n, _ in groups["Written by"]] == ["John Lennon", "Paul McCartney"]
    assert groups["Produced by"] == [["George Martin", None]]
    assert groups["Engineered by"] == [["Geoff Emerick", None]]


def test_credits_without_relationships_is_a_miss():
    assert credits.build_groups({"artist-credit": [{"artist": {"name": "X"}}], "relations": []}) == []


def test_fetch_credits_two_requests_and_picks_closest_length(monkeypatch):
    monkeypatch.setattr(credits, "MIN_INTERVAL", 0)
    rec = json.loads((FIX / "mb_recording.json").read_text(encoding="utf-8")); seen = []
    def h(req):
        seen.append(req.url.path)
        if "/isrc/" in req.url.path:
            return httpx.Response(200, json={"recordings": [{"id": "far", "length": 300000}, {"id": "close", "length": 124000}]})
        assert req.url.path.endswith("/recording/close") and "work-level-rels" in req.url.params["inc"]
        return httpx.Response(200, json=rec)
    r = credits.fetch_credits(client(h), track())
    assert r and r["groups"][0][0] == "Performed by" and len(seen) == 2


def test_credits_without_isrc_makes_no_request():
    def h(req): raise AssertionError("no request expected")
    assert credits.fetch_credits(client(h), track(isrc=None)) is None


# ---- art colours -------------------------------------------------------------

def png(colors):
    im = Image.new("RGB", (60, 60))
    for i, c in enumerate(colors):
        im.paste(c, (i * 60 // len(colors), 0, (i + 1) * 60 // len(colors), 60))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


def test_two_distinct_saturated_colours_are_chosen():
    out = art_color.colors_from_image(png([(200, 40, 40), (40, 60, 200), (235, 235, 235), (20, 20, 20)]))
    assert len(out) == 2 and out[0] != out[1] and all(c.startswith("#") and len(c) == 7 for c in out)


def test_monochrome_cover_still_gets_two_colours():
    out = art_color.colors_from_image(png([(120, 120, 120)]))
    assert out is None or len(out) == 2


def test_unreadable_image_is_none_and_missing_art_is_a_miss():
    assert art_color.colors_from_image(b"not an image") is None
    assert art_color.fetch_colors(client(lambda r: httpx.Response(404)), "https://img/x") is None
    with pytest.raises(Transient):
        art_color.fetch_colors(client(lambda r: httpx.Response(503)), "https://img/x")


# ---- last.fm -----------------------------------------------------------------

def test_lastfm_stats_with_and_without_a_linked_user():
    def h(req):
        assert req.url.params["method"] == "track.getInfo" and req.url.params["autocorrect"] == "1"
        t = {"listeners": "1234", "playcount": "9"}
        if "username" in req.url.params:
            t["userplaycount"] = "23"
        return httpx.Response(200, json={"track": t})
    assert lastfm.fetch_stats(client(h), track(), "K", None) == {"listeners": 1234}
    assert lastfm.fetch_stats(client(h), track(), "K", "anton") == {"listeners": 1234, "plays": 23}


def test_lastfm_unknown_track_is_a_miss():
    assert lastfm.fetch_stats(client(lambda r: httpx.Response(200, json={"error": 6, "message": "Track not found"})), track(), "K", None) is None


# ---- scrobble rules ----------------------------------------------------------

def st(track_, progress, playing=True, at=1_000_000_000_000):
    return PlayerState(status="ready", track=track_, is_playing=playing, progress_ms=progress, fetched_at_ms=at)


def test_scrobbles_once_after_half_the_song():
    t, tr = track(duration_ms=200_000), ScrobbleTracker()
    assert [e.kind for e in tr.observe(st(t, 0))] == ["now_playing"]
    out = []
    for p in range(5_000, 200_000, 5_000):
        out += tr.observe(st(t, p))
    assert [e.kind for e in out] == ["scrobble"]
    assert out[0].started_at == 1_000_000_000


def test_seeking_to_the_end_does_not_count_as_listening():
    t, tr = track(duration_ms=200_000), ScrobbleTracker()
    tr.observe(st(t, 0)); tr.observe(st(t, 190_000))
    assert tr.observe(st(t, 195_000)) == []


def test_paused_time_and_short_tracks_never_scrobble():
    t, tr = track(duration_ms=200_000), ScrobbleTracker()
    tr.observe(st(t, 0))
    for p in range(5_000, 150_000, 5_000):
        assert tr.observe(st(t, p, playing=False)) == []
    short, tr2 = track(id="s", duration_ms=25_000), ScrobbleTracker()
    assert tr2.observe(st(short, 0)) == []
    for p in range(5_000, 25_000, 5_000):
        assert tr2.observe(st(short, p)) == []


def test_four_minute_cap_for_long_tracks_and_replay_after_restart():
    t, tr = track(duration_ms=900_000), ScrobbleTracker()
    tr.observe(st(t, 0)); out = []
    for p in range(10_000, 260_000, 10_000):
        out += tr.observe(st(t, p))
    assert [e.kind for e in out] == ["scrobble"]
    tr.observe(st(t, 256_000))
    again = tr.observe(st(t, 1_000))  # same song restarted
    assert [e.kind for e in again] == ["now_playing"]


# ---- cache + manager ---------------------------------------------------------

def test_cache_hit_miss_and_expiry():
    c = Cache(":memory:")
    assert c.get("k", "lyrics") == (False, None)
    c.put("k", "lyrics", {"a": 1}, 1)
    assert c.get("k", "lyrics") == (True, {"a": 1})
    c.put("k", "credits", None, 1)  # confirmed miss
    assert c.get("k", "credits") == (True, None)
    c.put("k", "features", {"x": 1}, -1)  # already expired
    assert c.get("k", "features") == (False, None)


def test_lyric_search_across_cache_escapes_wildcards():
    c = Cache(":memory:")
    c.put("t1", "lyrics", {"track": {"id": "t1", "title": "A"}, "lines": [[3, "Counting the boats"], [9, "100% sure"]]}, 1)
    c.put("t2", "lyrics", {"track": {"id": "t2", "title": "B"}, "lines": [[1, "Nothing here"]]}, 1)
    assert c.search_lyrics("boats") == [{"track": {"id": "t1", "title": "A"}, "line": [3, "Counting the boats"]}]
    assert [h["track"]["id"] for h in c.search_lyrics("100%")] == ["t1"]
    assert c.search_lyrics("%%%") == [] and c.search_lyrics("ab") == []  # too short, and % is not a wildcard


def wait_for(cond, secs=3):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def make_enricher(handler, **cfg):
    got, c = [], Cache(":memory:")
    e = Enricher(Config(**cfg), c, got.append, http=client(handler), lastfm_user=lambda: None)
    return e, got, c


def test_manager_emits_each_source_and_skips_unconfigured_lastfm(monkeypatch):
    monkeypatch.setattr(credits, "MIN_INTERVAL", 0)
    def h(req):
        host = req.url.host
        if "lrclib" in host: return httpx.Response(200, json={"syncedLyrics": "[00:01.00]Hi"})
        if "recco" in host: return httpx.Response(200, json=RECCO)
        if "musicbrainz" in host: return httpx.Response(404)
        return httpx.Response(200, content=png([(200, 40, 40), (40, 60, 200)]))
    e, got, c = make_enricher(h)
    e.request(track())
    assert wait_for(lambda: len(got) == 4)  # lyrics, credits, features, art: not lastfm (no key)
    by = {g["kind"]: g for g in got}
    assert set(by) == {"lyrics", "credits", "features", "art"}
    assert by["lyrics"]["data"] == {"lines": [[1.0, "Hi"]]} and by["credits"]["data"] is None and not by["credits"]["error"]
    assert by["features"]["data"]["bpm"] == 97 and len(by["art"]["data"]) == 2
    assert c.search_lyrics("hi") == [] and c.get("3BQHpFgAp4l80e1XslIjNI", "lyrics")[1]["track"]["title"] == "Yesterday"


def test_transient_failure_is_reported_but_not_cached():
    calls = []
    def h(req):
        calls.append(1); return httpx.Response(429)
    e, got, c = make_enricher(h)
    e.request(track(), ("lyrics",))
    assert wait_for(lambda: len(got) == 1)
    assert got[0]["error"] is True and got[0]["data"] is None
    assert c.get(track().id, "lyrics") == (False, None)  # asked again next time


def test_second_request_is_served_from_cache():
    n = []
    def h(req):
        n.append(1); return httpx.Response(200, json={"syncedLyrics": "[00:01.00]Hi"})
    e, got, c = make_enricher(h)
    e.request(track(), ("lyrics",)); assert wait_for(lambda: len(got) == 1)
    first = len(n)
    e.request(track(), ("lyrics",)); assert wait_for(lambda: len(got) == 2)
    assert len(n) == first and got[1]["data"] == got[0]["data"]


def test_a_crashing_source_does_not_stop_the_others():
    def h(req):
        if "lrclib" in req.url.host: raise RuntimeError("bug")
        return httpx.Response(200, json=RECCO)
    e, got, c = make_enricher(h)
    e.request(track(), ("lyrics", "features"))
    assert wait_for(lambda: len(got) == 2)
    assert {g["kind"]: g["error"] for g in got} == {"lyrics": True, "features": False}


# ---- LRCLIB is rate limited: space requests out and retry once -------------------

def test_lyrics_retry_once_after_a_429_then_succeed():
    n = []
    def h(req):
        n.append(1)
        return httpx.Response(429) if len(n) == 1 else httpx.Response(200, json={"syncedLyrics": "[00:01.00]Hi"})
    assert lyrics.fetch_lyrics(client(h), track()) == {"lines": [[1.0, "Hi"]]} and len(n) == 2


def test_lyrics_requests_are_spaced_out(monkeypatch):
    import time as _t
    sleeps = []
    monkeypatch.setattr(lyrics, "MIN_INTERVAL", 0.8)
    monkeypatch.setattr(lyrics.time, "sleep", sleeps.append)
    monkeypatch.setattr(lyrics, "_last", [_t.monotonic()])  # a request was just made
    lyrics.fetch_lyrics(client(lambda r: httpx.Response(200, json={"syncedLyrics": "[00:01.00]Hi"})), track())
    assert sleeps and 0 < sleeps[0] <= 0.8
