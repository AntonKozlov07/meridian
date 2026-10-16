import json
import threading
from unittest.mock import MagicMock

from spotipy import SpotifyException

import meridian.sources.spotify.auth as auth_mod
from meridian.api import Api, friendly_error
from meridian.config import Config
from meridian.core.poller import Poller, retry_after
from meridian.core.state import LOGGED_OUT, SETUP_REQUIRED, PlayerState


def test_boot_without_client_id():
    assert Api(Config()).boot()["status"] == SETUP_REQUIRED


def test_boot_without_session_is_logged_out(monkeypatch):
    fake = MagicMock(); fake.has_session.return_value = False
    monkeypatch.setattr("meridian.api.SpotifyAuth", lambda *a: fake)
    assert Api(Config(spotify_client_id="abc")).boot()["status"] == LOGGED_OUT


def test_actions_need_a_session():
    r = Api(Config()).set_playing(True)
    assert r["ok"] is False and "Not connected" in r["error"]


def test_action_errors_become_messages_and_success_pokes():
    api = Api(Config()); api._source = MagicMock(); api._poller = MagicMock()
    assert api.next()["ok"] is True
    api._poller.poke.assert_called_once()
    api._source.next.side_effect = SpotifyException(403, -1, "x", reason="PREMIUM_REQUIRED")
    r = api.next()
    assert r == {"ok": False, "error": "Spotify Premium is required to control playback."}


def test_friendly_errors():
    assert "No active" in friendly_error(SpotifyException(404, -1, "x", reason="NO_ACTIVE_DEVICE"))
    assert "rate" in friendly_error(SpotifyException(429, -1, "x"))


def test_logout_pushes_logged_out():
    api = Api(Config()); api._auth = MagicMock(); pushed = []
    api._attach(pushed.append); api.logout()
    assert pushed[0]["status"] == LOGGED_OUT and api._auth.logout.called


def test_poller_pushes_and_survives_errors():
    src = MagicMock(); got = []; done = threading.Event()
    src.poll.side_effect = [RuntimeError("boom"), PlayerState(), PlayerState()]
    def push(s):
        got.append(s); done.set()
    p = Poller(src, push, interval=0.01); p.start()
    assert done.wait(2); p.stop()
    assert got


def test_retry_after():
    e = SpotifyException(429, -1, "x", headers={"Retry-After": "7"})
    assert retry_after(e) == 8 and retry_after(RuntimeError()) is None


def test_keyring_cache_roundtrip_and_fallback(monkeypatch):
    store = {}
    monkeypatch.setattr(auth_mod.keyring, "get_password", lambda s, a: store.get((s, a)))
    monkeypatch.setattr(auth_mod.keyring, "set_password", lambda s, a, v: store.__setitem__((s, a), v))
    monkeypatch.setattr(auth_mod.keyring, "delete_password", lambda s, a: store.pop((s, a), None))
    h = auth_mod.KeyringCacheHandler()
    assert h.get_cached_token() is None
    h.save_token_to_cache({"access_token": "a"})
    assert json.loads(store[("meridian", "spotify-token")])["access_token"] == "a"
    assert h.get_cached_token() == {"access_token": "a"}
    h.clear(); assert h.get_cached_token() is None


def test_keyring_unavailable_falls_back_to_memory(monkeypatch):
    from keyring.errors import NoKeyringError
    def boom(*a): raise NoKeyringError()
    for n in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(auth_mod.keyring, n, boom)
    h = auth_mod.KeyringCacheHandler()
    h.save_token_to_cache({"access_token": "m"})
    assert h.get_cached_token() == {"access_token": "m"}


def test_scopes_cover_playback_and_library():
    for s in ("user-modify-playback-state", "user-read-recently-played", "user-library-read", "playlist-read-private"):
        assert s in auth_mod.SCOPES
