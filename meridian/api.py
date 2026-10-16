"""Methods the UI calls through window.pywebview.api.*.

Everything with a leading underscore is hidden from the page (pywebview only exposes
public methods). The page never sees a token or calls an outside API itself.
"""
from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable

import requests
from spotipy import SpotifyException

from meridian import config as config_mod
from meridian.config import Config
from meridian.core.poller import Poller
from meridian.core.source import PlayerSource
from meridian.core.state import CONNECTING, ERROR, LOGGED_OUT, SETUP_REQUIRED, WAITING, PlayerState
from meridian.sources.spotify.auth import SpotifyAuth
from meridian.sources.spotify.login import LoginError
from meridian.sources.spotify.source import SpotifySource

log = logging.getLogger(__name__)


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

    def _attach(self, push: Callable[[dict], None]) -> None:
        self._push = push

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
        self._poller = Poller(self._source, lambda s: self._push(s.to_dict()), on_error=self._poll_failed)
        self._poller.start()

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
