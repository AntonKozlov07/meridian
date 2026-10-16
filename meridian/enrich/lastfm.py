"""Last.fm: play counts and listeners (read), linking an account, and scrobbling (write).

Stats use the public track.getInfo call. Linking uses Last.fm's web auth, so Meridian never sees a password;
the session key is kept in the OS keychain.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable

import httpx
import keyring
import pylast
from keyring.errors import KeyringError

from meridian.core.state import Track
from meridian.enrich.common import get_json

log = logging.getLogger(__name__)
API = "https://ws.audioscrobbler.com/2.0/"
SERVICE, ACCOUNT = "meridian", "lastfm"


def load_link() -> dict | None:
    try:
        raw = keyring.get_password(SERVICE, ACCOUNT)
    except KeyringError:
        return None
    return json.loads(raw) if raw else None


def save_link(username: str, session_key: str) -> None:
    try:
        keyring.set_password(SERVICE, ACCOUNT, json.dumps({"username": username, "session_key": session_key}))
    except KeyringError as e:
        log.warning("could not store the Last.fm session in the keychain: %s", e)


def clear_link() -> None:
    try:
        keyring.delete_password(SERVICE, ACCOUNT)
    except KeyringError:
        pass


def fetch_stats(client: httpx.Client, track: Track, api_key: str, username: str | None) -> dict | None:
    """{'listeners': int, 'plays': int|None}; plays only when an account is linked. None if Last.fm does not know the track."""
    artist = track.artists[0] if track.artists else track.artist
    params = {"method": "track.getInfo", "api_key": api_key, "artist": artist, "track": track.title,
              "autocorrect": 1, "format": "json"}
    if username:
        params["username"] = username
    data = get_json(client, API, params)
    t = (data or {}).get("track")
    if not t:
        return None  # includes Last.fm's "Track not found" (error 6)
    out: dict = {}
    try:
        out["listeners"] = int(t["listeners"])
    except (KeyError, TypeError, ValueError):
        pass
    if username:
        try:
            out["plays"] = int(t["userplaycount"])
        except (KeyError, TypeError, ValueError):
            pass
    return out or None


def link_account(api_key: str, api_secret: str, open_browser: Callable[[str], object],
                 cancel: threading.Event, timeout: float = 120, poll: float = 2.0) -> tuple[str, str]:
    """Opens Last.fm's approval page and waits. Returns (username, session_key). Raises RuntimeError with a usable message."""
    network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
    gen = pylast.SessionKeyGenerator(network)
    url = gen.get_web_auth_url()
    open_browser(url)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not cancel.is_set():
        try:
            key, user = gen.get_web_auth_session_key_username(url)
            return user, key
        except pylast.WSError:
            cancel.wait(poll)  # not approved yet
        except pylast.NetworkError as e:
            raise RuntimeError("Cannot reach Last.fm. Check your connection.") from e
    raise RuntimeError("Linking cancelled." if cancel.is_set() else "Timed out waiting for Last.fm approval.")


def make_network(api_key: str, api_secret: str, username: str, session_key: str) -> pylast.LastFMNetwork:
    return pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret, username=username, session_key=session_key)
