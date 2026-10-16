import time
from unittest.mock import MagicMock

from meridian import config
from meridian.api import Api
from meridian.config import Config
from meridian.core.state import PlayerState, Track
from meridian.enrich.cache import Cache


def trk(i="t1", secs=200):
    return Track(id=i, uri=f"spotify:track:{i}", title="Song", artist="A", album="Al", year=2024, duration_ms=secs * 1000,
                 art_url=None, artists=["A"])


def ready(track, progress=0, playing=True):
    return PlayerState(status="ready", track=track, progress_ms=progress, is_playing=playing,
                       fetched_at_ms=int(time.time() * 1000))


def test_new_track_triggers_enrichment_once_and_the_page_still_updates():
    api = Api(Config()); pushed = []; api._attach(pushed.append)
    api._enricher = MagicMock()
    api._on_state(ready(trk("a"))); api._on_state(ready(trk("a"), 5000)); api._on_state(ready(trk("b")))
    assert len(pushed) == 3
    assert [c.args[0].id for c in api._enricher.request.call_args_list] == ["a", "b"]


def test_enrichment_failure_never_blocks_the_page():
    api = Api(Config()); pushed = []; api._attach(pushed.append)
    api._enricher = MagicMock(); api._enricher.request.side_effect = RuntimeError("boom")
    api._on_state(ready(trk()))
    assert len(pushed) == 1


def test_open_link_only_allows_https_attribution_hosts(monkeypatch):
    opened = []
    monkeypatch.setattr("meridian.api.webbrowser.open", opened.append)
    api = Api(Config())
    assert api.open_link("https://getsongbpm.com")["ok"] is True
    for bad in ["http://getsongbpm.com", "https://evil.example/x", "file:///etc/passwd", "javascript:alert(1)"]:
        assert api.open_link(bad)["ok"] is False
    assert opened == ["https://getsongbpm.com"]


def test_integrations_reflect_configuration(monkeypatch):
    monkeypatch.setattr("meridian.api.lastfm.load_link", lambda: None)
    assert Api(Config()).integrations()["lastfm"] == {"configured": False, "can_link": False, "linked": False, "username": None}
    r = Api(Config(lastfm_api_key="k")).integrations()["lastfm"]
    assert r["configured"] and not r["can_link"]
    monkeypatch.setattr("meridian.api.lastfm.load_link", lambda: {"username": "anton", "session_key": "s"})
    assert Api(Config(lastfm_api_key="k", lastfm_api_secret="s")).integrations()["lastfm"]["username"] == "anton"


def test_link_requires_key_and_secret():
    r = Api(Config(lastfm_api_key="k")).link_lastfm()
    assert r["ok"] is False and "LASTFM_API_SECRET" in r["error"]


def test_link_saves_session_and_refreshes_stats(monkeypatch):
    saved = {}
    monkeypatch.setattr("meridian.api.lastfm.link_account", lambda *a, **k: ("anton", "SK"))
    monkeypatch.setattr("meridian.api.lastfm.save_link", lambda u, k: saved.update(u=u, k=k))
    monkeypatch.setattr("meridian.api.lastfm.load_link", lambda: {"username": "anton", "session_key": "SK"})
    api = Api(Config(lastfm_api_key="k", lastfm_api_secret="s")); api._enricher = MagicMock(); api._current_track = trk()
    r = api.link_lastfm()
    assert r["ok"] and r["integrations"]["lastfm"]["linked"] and saved == {"u": "anton", "k": "SK"}
    api._enricher.request.assert_called_once()
    assert api._enricher.request.call_args.args[1] == ("lastfm",)


def test_scrobble_only_when_linked_and_never_raises():
    api = Api(Config(lastfm_api_key="k", lastfm_api_secret="s"))
    from meridian.enrich.scrobble import Event
    ev = Event("scrobble", trk(), 1000)
    api._scrobble(ev)  # not linked: silently nothing
    net = MagicMock(); api._lastfm_net = net
    api._scrobble(ev)
    net.scrobble.assert_called_once_with("A", "Song", 1000, album="Al", duration=200)
    net.scrobble.side_effect = RuntimeError("down")
    api._scrobble(ev)  # a Last.fm outage must not raise


def test_search_adds_lyric_hits_from_the_cache():
    api = Api(Config()); src = MagicMock(); api._source = src
    from meridian.core.state import SearchResults
    src.search.return_value = SearchResults(query="boats")
    api._cache = Cache(":memory:")
    api._cache.put("t1", "lyrics", {"track": {"id": "t1", "title": "A"}, "lines": [[3, "Counting the boats"]]}, 1)
    r = api.search("boats")
    assert r["ok"] and r["data"]["lyric_hits"][0]["line"] == [3, "Counting the boats"]


def test_play_at_passes_milliseconds():
    api = Api(Config()); api._source = MagicMock()
    api.play_at("spotify:track:x", 31000)
    api._source.play_at.assert_called_once_with("spotify:track:x", 31000)
