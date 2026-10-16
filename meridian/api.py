"""Methods the UI calls through window.pywebview.api.*.

Everything with a leading underscore is hidden from the page (pywebview only exposes
public methods). The page never sees a token or calls an outside API itself.
"""
from __future__ import annotations

import logging
import re
import threading
import webbrowser
from dataclasses import asdict
from urllib.parse import urlparse
from collections.abc import Callable

import requests
from spotipy import SpotifyException

from meridian import config as config_mod
from meridian.config import Config
from meridian.core.poller import Poller
from meridian.core.source import PlayerSource
from meridian.settings import Settings
from meridian.enrich import lastfm
from meridian.enrich.cache import Cache
from meridian.enrich.manager import Enricher
from meridian.enrich.scrobble import Event, ScrobbleTracker
from meridian.core.state import CONNECTING, ERROR, LOGGED_OUT, SETUP_REQUIRED, WAITING, PlayerState
from meridian.sources.spotify.auth import SpotifyAuth
from meridian.sources.spotify.login import LoginError
from meridian.sources.spotify.source import SpotifySource

log = logging.getLogger(__name__)

LINK_HOSTS = {"getsongbpm.com", "www.getsongbpm.com", "lrclib.net", "musicbrainz.org", "www.last.fm", "last.fm"}


class Api:
    def __init__(self, config: Config):
        self._cfg = config
        self._auth: SpotifyAuth | None = None
        self._source: PlayerSource | None = None
        self._poller: Poller | None = None
        self._push: Callable[[dict], None] = lambda s: None
        self._last_track_id: str | None = None
        self._lock = threading.Lock()
        self._login_cancel: threading.Event | None = None
        self._cache: Cache | None = None
        self._settings = Settings()
        self._enricher: Enricher | None = None
        self._push_enrich: Callable[[dict], None] = lambda e: None
        self._tracker = ScrobbleTracker()
        self._current_track = None
        self._lastfm_link: dict | None = None
        self._lastfm_net = None
        self._lastfm_cancel: threading.Event | None = None

    def _attach(self, push: Callable[[dict], None], push_enrich: Callable[[dict], None] | None = None) -> None:
        self._push = push
        if push_enrich:
            self._push_enrich = push_enrich

    def _shutdown(self) -> None:
        """Window closed: stop polling and stop pushing into a page that no longer exists."""
        self._push = lambda s: None
        self._push_enrich = lambda e: None
        if self._enricher:
            self._enricher.shutdown()
        if self._poller:
            self._poller.stop()

    # -- session -------------------------------------------------------
    def boot(self) -> dict:
        """Called once by the page. Resumes a stored session without opening a browser."""
        if not self._cfg.spotify_client_id:
            return PlayerState(status=SETUP_REQUIRED).to_dict()
        self._auth = SpotifyAuth(self._cfg.spotify_client_id, self._cfg.spotify_redirect_uri)
        if self._auth.has_session():
            self._start()
            return PlayerState(status=CONNECTING).to_dict()
        return PlayerState(status=LOGGED_OUT).to_dict()

    def save_client_id(self, client_id: str) -> dict:
        """Saves the client ID typed into the setup screen to .env and carries on with sign-in."""
        client_id = (client_id or "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{32}", client_id):
            return self._fail("A client ID is 32 letters and numbers. Copy it from your app's page in the Spotify dashboard.")
        config_mod.save_env_value("SPOTIFY_CLIENT_ID", client_id)
        self._cfg = config_mod.load()
        return {"ok": True, "error": None, "state": self.boot()}

    def login(self) -> dict:
        """Opens the browser for Spotify consent and blocks until it finishes."""
        if not self._auth:
            return self._fail("Spotify is not configured.")
        if self._login_cancel and not self._login_cancel.is_set():
            return self._fail("Sign-in is already open in your browser.")
        self._login_cancel = cancel = threading.Event()
        try:
            self._auth.login(
                on_url=lambda url: self._push(PlayerState(status=WAITING, message=url).to_dict()),
                cancel=cancel,
            )
        except LoginError as e:
            return self._login_failed(str(e))
        except Exception as e:
            log.exception("login crashed")
            return self._login_failed(f"Sign-in failed unexpectedly ({type(e).__name__}: {e}). See the log for details.")
        finally:
            cancel.set()
        self._start()
        self._push(PlayerState(status=CONNECTING).to_dict())
        return self._ok()

    def cancel_login(self) -> dict:
        if self._login_cancel:
            self._login_cancel.set()
        return self._ok()

    def _login_failed(self, msg: str) -> dict:
        log.warning("login failed: %s", msg)
        self._push(PlayerState(status=LOGGED_OUT, message=msg).to_dict())
        return self._fail(msg)

    def logout(self) -> dict:
        if self._poller:
            self._poller.stop()
        self._poller = self._source = None
        if self._auth:
            self._auth.logout()
        self._push(PlayerState(status=LOGGED_OUT).to_dict())
        return self._ok()

    def _start(self) -> None:
        assert self._auth
        self._source = SpotifySource(self._auth.client())
        if self._poller:
            self._poller.stop()
        if not self._enricher:
            self._cache = Cache()
            self._lastfm_link = lastfm.load_link()
            self._enricher = Enricher(self._cfg, self._cache, lambda e: self._push_enrich(e),
                                      lastfm_user=lambda: (self._lastfm_link or {}).get("username"))
        self._poller = Poller(self._source, self._on_state, on_error=self._poll_failed)
        self._poller.start()

    def _on_state(self, state: PlayerState) -> None:
        """Every poll: update the page, then start enrichment and scrobbling. Neither may disturb playback."""
        self._push(state.to_dict())
        try:
            if state.status == "ready" and state.track:
                if self._current_track is None or state.track.id != self._current_track.id:
                    self._current_track = state.track
                    if self._enricher:
                        self._enricher.request(state.track)
                for ev in self._tracker.observe(state):
                    threading.Thread(target=self._scrobble, args=(ev,), daemon=True).start()
        except Exception:
            log.exception("post-poll work failed")

    def _scrobble(self, ev: Event) -> None:
        if not self._lastfm_net:
            if not (self._lastfm_link and self._cfg.lastfm_api_key and self._cfg.lastfm_api_secret):
                return
            self._lastfm_net = lastfm.make_network(self._cfg.lastfm_api_key, self._cfg.lastfm_api_secret,
                                                   self._lastfm_link["username"], self._lastfm_link["session_key"])
        t = ev.track
        artist = t.artists[0] if t.artists else t.artist
        try:
            if ev.kind == "now_playing":
                self._lastfm_net.update_now_playing(artist, t.title, album=t.album or None, duration=t.duration_ms // 1000)
            else:
                self._lastfm_net.scrobble(artist, t.title, ev.started_at, album=t.album or None, duration=t.duration_ms // 1000)
        except Exception as e:
            log.warning("Last.fm %s failed: %s", ev.kind, e)

    def _poll_failed(self, exc: Exception, failures: int) -> None:
        """Turns a failing poll into a screen that says why, instead of an endless spinner."""
        if isinstance(exc, SpotifyException) and exc.http_status == 401:
            if self._auth:
                self._auth.logout()
            self._push(PlayerState(status=LOGGED_OUT, message="Your Spotify session expired. Connect again.").to_dict())
        elif isinstance(exc, SpotifyException) and exc.http_status == 403:
            self._push(PlayerState(status=ERROR, message=(
                "Spotify refused this account. While your app is in development mode, only people added under "
                "User Management in the Spotify dashboard can use it. Add your Spotify email there, then try again."
            )).to_dict())
        elif isinstance(exc, SpotifyException) and exc.http_status == 429:
            pass  # the poller already waits out Retry-After
        elif failures >= 2:
            offline = isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
            self._push(PlayerState(status=ERROR, message=(
                "Cannot reach Spotify. Check your internet connection." if offline
                else f"Spotify is not responding as expected ({type(exc).__name__})."
            )).to_dict())

    # -- transport -----------------------------------------------------
    def set_playing(self, playing: bool) -> dict:
        return self._do(lambda s: s.play() if playing else s.pause())

    def next(self) -> dict:
        return self._do(lambda s: s.next())

    def previous(self) -> dict:
        return self._do(lambda s: s.previous())

    def seek(self, position_ms: int) -> dict:
        return self._do(lambda s: s.seek(position_ms))

    def set_volume(self, percent: int) -> dict:
        return self._do(lambda s: s.set_volume(percent))

    def set_shuffle(self, on: bool) -> dict:
        return self._do(lambda s: s.set_shuffle(on))

    def set_repeat(self, mode: str) -> dict:
        return self._do(lambda s: s.set_repeat(mode))

    def transfer(self, device_id: str) -> dict:
        return self._do(lambda s: s.transfer(device_id))

    def set_saved(self, track_id: str, saved: bool) -> dict:
        return self._do(lambda s: s.set_saved(track_id, saved))

    def add_to_queue(self, uri: str) -> dict:
        return self._do(lambda s: s.add_to_queue(uri))

    def play_track(self, uri: str) -> dict:
        return self._do(lambda s: s.play_track(uri))

    def jump_ahead(self, steps: int, uri: str) -> dict:
        return self._do(lambda s: s.jump_ahead(int(steps), uri))

    def play_uri(self, uri: str, kind: str) -> dict:
        return self._do(lambda s: s.play_uri(uri, kind))

    def get_library(self, force: bool = False) -> dict:
        return self._data(lambda s: asdict(s.library(force)))

    def search(self, query: str) -> dict:
        def read(s):
            data = asdict(s.search(query))
            data["lyric_hits"] = self._cache.search_lyrics(query) if self._cache else []
            return data
        return self._data(read)

    def play_at(self, uri: str, position_ms: int) -> dict:
        return self._do(lambda s: s.play_at(uri, int(position_ms)))

    def get_settings(self) -> dict:
        return self._settings.get_all()

    def set_setting(self, key: str, value) -> dict:
        return self._ok() if self._settings.set(key, value) else self._fail("Unknown setting.")

    def integrations(self) -> dict:
        """What the About panel can offer: Last.fm stats need a key, linking needs the secret too."""
        link = self._lastfm_link or lastfm.load_link()
        return {"lastfm": {"configured": bool(self._cfg.lastfm_api_key),
                           "can_link": bool(self._cfg.lastfm_api_key and self._cfg.lastfm_api_secret),
                           "linked": bool(link), "username": (link or {}).get("username")}}

    def link_lastfm(self) -> dict:
        """Opens Last.fm's approval page and waits for the user to approve."""
        if not (self._cfg.lastfm_api_key and self._cfg.lastfm_api_secret):
            return self._fail("Add LASTFM_API_KEY and LASTFM_API_SECRET to .env to link Last.fm.")
        self._lastfm_cancel = cancel = threading.Event()
        try:
            user, key = lastfm.link_account(self._cfg.lastfm_api_key, self._cfg.lastfm_api_secret, webbrowser.open, cancel)
        except RuntimeError as e:
            return self._fail(str(e))
        lastfm.save_link(user, key)
        self._lastfm_link, self._lastfm_net = {"username": user, "session_key": key}, None
        if self._enricher and self._current_track:
            self._enricher.request(self._current_track, ("lastfm",))
        return {"ok": True, "error": None, "integrations": self.integrations()}

    def unlink_lastfm(self) -> dict:
        lastfm.clear_link()
        self._lastfm_link = self._lastfm_net = None
        if self._enricher and self._current_track:
            self._enricher.request(self._current_track, ("lastfm",))
        return {"ok": True, "error": None, "integrations": self.integrations()}

    def open_link(self, url: str) -> dict:
        """Opens an attribution link in the real browser (a link inside the window would navigate away from the app)."""
        if urlparse(url).scheme == "https" and urlparse(url).hostname in LINK_HOSTS:
            webbrowser.open(url)
            return self._ok()
        return self._fail("That link is not allowed.")

    def refresh(self) -> dict:
        if self._poller:
            self._poller.poke()
        return self._ok()

    # -- helpers -------------------------------------------------------
    def _do(self, action: Callable[[PlayerSource], None]) -> dict:
        if not self._source:
            return self._fail("Not connected to Spotify.")
        try:
            action(self._source)
        except SpotifyException as e:
            return self._fail(friendly_error(e))
        except Exception as e:
            log.warning("action failed: %s", e)
            return self._fail("Something went wrong talking to Spotify.")
        if self._poller:
            self._poller.poke(delay=0.4)
        return self._ok()

    def _data(self, read: Callable[[PlayerSource], dict]) -> dict:
        """Like _do, but returns what was read: {ok, error, data}."""
        if not self._source:
            return self._fail("Not connected to Spotify.")
        try:
            return {"ok": True, "error": None, "data": read(self._source)}
        except SpotifyException as e:
            return self._fail(friendly_error(e))
        except Exception as e:
            log.warning("read failed: %s", e)
            return self._fail("Something went wrong talking to Spotify.")

    @staticmethod
    def _ok() -> dict:
        return {"ok": True, "error": None}

    @staticmethod
    def _fail(msg: str) -> dict:
        return {"ok": False, "error": msg}


def friendly_error(e: SpotifyException) -> str:
    reason = (getattr(e, "reason", "") or "").upper()
    if e.http_status == 403 and "PREMIUM" in reason:
        return "Spotify Premium is required to control playback."
    if e.http_status == 404 or "NO_ACTIVE_DEVICE" in reason:
        return "No active Spotify device. Start playing on one, then try again."
    if e.http_status == 429:
        return "Spotify is rate limiting requests. Try again in a moment."
    if e.http_status == 403:
        return "Spotify refused that action on this device."
    return "Spotify could not do that."
