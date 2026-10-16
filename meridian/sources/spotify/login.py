"""Spotify sign-in (OAuth authorization code + PKCE) with a local callback server.

Replaces spotipy's built-in login, which answers exactly one request (a stray favicon
or browser preconnect breaks it) and reports failures poorly. Every failure here ends
in a LoginError whose message says what to do about it.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import threading
import time
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
TIMEOUT_S = 180


class LoginError(Exception):
    """A failure whose message is safe and useful to show the user."""


def parse_redirect(redirect_uri: str) -> tuple[str, int, str]:
    u = urlparse(redirect_uri)
    if u.scheme != "http" or u.hostname not in ("127.0.0.1", "[::1]", "::1"):
        raise LoginError(
            f"Redirect URI {redirect_uri} will not work. Spotify only allows http://127.0.0.1:<port>/<path> "
            "for desktop apps ('localhost' is rejected). Use http://127.0.0.1:8888/callback."
        )
    if not u.port:
        raise LoginError(f"Redirect URI {redirect_uri} needs a port, for example http://127.0.0.1:8888/callback.")
    return u.hostname, u.port, u.path or "/"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def make_pkce() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(64))  # 86 chars, within the 43-128 allowed
    return verifier, _b64url(hashlib.sha256(verifier.encode()).digest())


_PAGE = """<!doctype html><meta charset="utf-8"><title>Meridian</title>
<body style="margin:0;display:grid;place-items:center;height:100vh;background:#131210;color:#f2eee8;font:15px system-ui,sans-serif">
<div style="max-width:420px;padding:24px"><h2 style="margin:0 0 8px;font-weight:600">{title}</h2>
<p style="margin:0;color:#a29c93;line-height:1.5">{body}</p></div></body>"""


def _make_handler(path: str, result: dict):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            if u.path != path:  # favicon, preconnects and scanners must not end the login
                self.send_response(404)
                self.end_headers()
                return
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if "code" not in q and "error" not in q:
                self.send_response(400)
                self.end_headers()
                return
            result.update(q)
            ok = "code" in q
            body = _PAGE.format(
                title="You're connected" if ok else "Sign-in did not finish",
                body="You can close this tab and go back to Meridian." if ok
                else "Go back to Meridian and try again.",
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # keep the console quiet
            pass

    return Handler


def run_login(
    client_id: str,
    redirect_uri: str,
    scope: str,
    on_url: Callable[[str], None] = lambda url: None,
    cancel: threading.Event | None = None,
    open_browser: Callable[[str], object] = webbrowser.open,
    timeout: float = TIMEOUT_S,
    http: httpx.Client | None = None,
) -> dict:
    """Blocks until the user finishes in the browser. Returns spotipy-compatible token info."""
    host, port, path = parse_redirect(redirect_uri)
    cancel = cancel or threading.Event()
    verifier, challenge = make_pkce()
    state = secrets.token_urlsafe(16)
    url = AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri, "scope": scope,
        "state": state, "code_challenge_method": "S256", "code_challenge": challenge,
    })

    result: dict = {}
    try:
        server = HTTPServer((host.strip("[]"), port), _make_handler(path, result))
    except OSError as e:
        raise LoginError(
            f"Port {port} is already in use ({e.strerror or e}). Close the other program using it, or pick another "
            "port in SPOTIFY_REDIRECT_URI and add the same URI in the Spotify dashboard."
        ) from e
    server.timeout = 0.3
    try:
        on_url(url)
        if not open_browser(url):
            log.warning("could not open a browser; the link was shown in the app instead")
        deadline = time.monotonic() + timeout
        while not result:
            if cancel.is_set():
                raise LoginError("Sign-in cancelled.")
            if time.monotonic() > deadline:
                raise LoginError(
                    "Timed out waiting for Spotify. If the Spotify page said 'INVALID_CLIENT: Invalid redirect URI', "
                    f"add exactly {redirect_uri} under Redirect URIs in your app's settings and press Save."
                )
            server.handle_request()
    finally:
        server.server_close()

    if "error" in result:
        if result["error"] == "access_denied":
            raise LoginError("You declined access on Spotify's page. Press Connect to try again.")
        raise LoginError(f"Spotify returned an error: {result['error']}")
    if result.get("state") != state:
        raise LoginError("The sign-in response did not match this attempt (an old browser tab?). Try again.")
    return _exchange(client_id, redirect_uri, result["code"], verifier, http)


def _exchange(client_id: str, redirect_uri: str, code: str, verifier: str, http: httpx.Client | None) -> dict:
    client = http or httpx.Client(timeout=15)
    try:
        r = client.post(TOKEN_URL, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
            "client_id": client_id, "code_verifier": verifier,
        })
    except httpx.HTTPError as e:
        raise LoginError(f"Could not reach Spotify to finish signing in ({type(e).__name__}). Check your connection.") from e
    if r.status_code != 200:
        try:
            body = r.json()
        except ValueError:
            body = {}
        err, desc = body.get("error", ""), body.get("error_description", "")
        if err == "invalid_client":
            raise LoginError("Spotify does not recognise this client ID. Copy it again from your app's settings.")
        raise LoginError(f"Spotify rejected the sign-in ({r.status_code}: {desc or err or 'no detail'}).")
    token = r.json()
    token["expires_at"] = int(time.time()) + int(token.get("expires_in", 3600))
    return token
