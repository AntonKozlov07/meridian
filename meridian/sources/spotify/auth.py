"""Spotify PKCE login. Tokens live in the OS keychain, never in a file."""
from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable

import keyring
import spotipy
from keyring.errors import KeyringError
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyPKCE

from meridian.sources.spotify.login import run_login

log = logging.getLogger(__name__)

SERVICE = "meridian"
ACCOUNT = "spotify-token"

# Requested once so later steps (library, history, likes) need no second login.
SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-read-recently-played",
    "user-read-private",
    "user-library-read",
    "user-library-modify",
    "playlist-read-private",
    "playlist-read-collaborative",
])


class KeyringCacheHandler(CacheHandler):
    """Stores the token JSON in the keychain; falls back to memory if no keychain exists."""

    def __init__(self) -> None:
        self._memory: dict | None = None

    def get_cached_token(self) -> dict | None:
        try:
            raw = keyring.get_password(SERVICE, ACCOUNT)
        except KeyringError as e:
            log.warning("keychain unavailable, using memory only: %s", e)
            return self._memory
        return json.loads(raw) if raw else None

    def save_token_to_cache(self, token_info: dict) -> None:
        self._memory = token_info
        try:
            keyring.set_password(SERVICE, ACCOUNT, json.dumps(token_info))
        except KeyringError as e:
            log.warning("could not save token to keychain: %s", e)

    def clear(self) -> None:
        self._memory = None
        try:
            keyring.delete_password(SERVICE, ACCOUNT)
        except KeyringError:
            pass


class SpotifyAuth:
    def __init__(self, client_id: str, redirect_uri: str):
        self.cache = KeyringCacheHandler()
        self.pkce = SpotifyPKCE(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=SCOPES,
            cache_handler=self.cache,
            open_browser=True,
        )

    def has_session(self) -> bool:
        """True if a stored token is usable (refreshing it if it expired). No browser."""
        token = self.cache.get_cached_token()
        if not token:
            return False
        try:
            return bool(self.pkce.validate_token(token))
        except Exception as e:
            log.info("stored token rejected: %s", e)
            return False

    def login(self, on_url: Callable[[str], None] = lambda url: None, cancel: threading.Event | None = None) -> None:
        """Opens the browser and blocks until the user finishes. Raises LoginError with a usable message."""
        token = run_login(self.pkce.client_id, self.pkce.redirect_uri, SCOPES, on_url=on_url, cancel=cancel)
        self.cache.save_token_to_cache(token)

    def logout(self) -> None:
        self.cache.clear()

    def client(self) -> spotipy.Spotify:
        # retries=0: 429s surface to the poller, which honours Retry-After
        return spotipy.Spotify(auth_manager=self.pkce, retries=0, requests_timeout=8)
