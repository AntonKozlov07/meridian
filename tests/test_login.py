import json
import threading
import urllib.request
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from meridian import config
from meridian.api import Api
from meridian.config import Config
from meridian.core.state import ERROR, LOGGED_OUT, SETUP_REQUIRED, WAITING
from meridian.sources.spotify import login as L


def free_port():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def token_client(status=200, body=None):
    seen = {}
    def handler(req):
        seen["form"] = parse_qs(req.content.decode())
        return httpx.Response(status, json=body if body is not None else
                              {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600, "scope": "x", "token_type": "Bearer"})
    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def browser(redirect, mutate=None, noise=True):
    """A fake browser: hits favicon first (the thing that breaks spotipy), then the redirect."""
    def open_url(url):
        q = parse_qs(urlparse(url).query)
        def go():
            base = f"http://127.0.0.1:{urlparse(redirect).port}"
            if noise:
                try: urllib.request.urlopen(base + "/favicon.ico")
                except Exception: pass
            params = {"code": "CODE", "state": q["state"][0]}
            if mutate: params = mutate(params)
            urllib.request.urlopen(base + urlparse(redirect).path + "?" + "&".join(f"{k}={v}" for k, v in params.items())).read()
        threading.Thread(target=go).start()
        return True
    return open_url


def run(redirect, **kw):
    http, seen = kw.pop("http", None) or token_client()
    tok = L.run_login("cid", redirect, "scope-a scope-b", http=http, timeout=5, **kw)
    return tok, seen


def test_login_survives_a_favicon_request_and_exchanges_the_code():
    redirect = f"http://127.0.0.1:{free_port()}/callback"
    tok, seen = run(redirect, open_browser=browser(redirect))
    assert tok["access_token"] == "AT" and tok["refresh_token"] == "RT" and tok["expires_at"] > 0
    f = seen["form"]
    assert f["grant_type"] == ["authorization_code"] and f["code"] == ["CODE"] and f["client_id"] == ["cid"]
    assert len(f["code_verifier"][0]) >= 43


def test_authorize_url_has_s256_challenge_and_state():
    redirect = f"http://127.0.0.1:{free_port()}/callback"
    urls = []
    run(redirect, open_browser=browser(redirect), on_url=urls.append)
    q = parse_qs(urlparse(urls[0]).query)
    assert q["code_challenge_method"] == ["S256"] and q["response_type"] == ["code"]
    assert q["scope"] == ["scope-a scope-b"] and q["redirect_uri"] == [redirect] and q["state"]


def test_pkce_challenge_matches_verifier():
    import base64, hashlib
    v, c = L.make_pkce()
    assert c == base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


def test_denied_access_has_a_clear_message():
    redirect = f"http://127.0.0.1:{free_port()}/callback"
    with pytest.raises(L.LoginError, match="declined"):
        run(redirect, open_browser=browser(redirect, mutate=lambda p: {"error": "access_denied", "state": p["state"]}))


def test_state_mismatch_is_rejected():
    redirect = f"http://127.0.0.1:{free_port()}/callback"
    with pytest.raises(L.LoginError, match="did not match"):
        run(redirect, open_browser=browser(redirect, mutate=lambda p: {"code": "C", "state": "forged"}))


def test_timeout_mentions_the_redirect_uri_fix():
    redirect = f"http://127.0.0.1:{free_port()}/callback"
    with pytest.raises(L.LoginError, match="Redirect URIs"):
        L.run_login("cid", redirect, "s", open_browser=lambda u: True, timeout=0.5)


def test_cancel_stops_the_wait():
    redirect = f"http://127.0.0.1:{free_port()}/callback"
    ev = threading.Event(); ev.set()
    with pytest.raises(L.LoginError, match="cancelled"):
        L.run_login("cid", redirect, "s", cancel=ev, open_browser=lambda u: True, timeout=5)


def test_busy_port_is_explained():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(); port = s.getsockname()[1]
    try:
        with pytest.raises(L.LoginError, match="already in use"):
            L.run_login("cid", f"http://127.0.0.1:{port}/callback", "s", open_browser=lambda u: True, timeout=1)
    finally:
        s.close()


@pytest.mark.parametrize("uri", ["http://localhost:8888/callback", "https://127.0.0.1:8888/callback", "http://127.0.0.1/callback"])
def test_bad_redirect_uris_are_rejected_with_advice(uri):
    with pytest.raises(L.LoginError):
        L.parse_redirect(uri)


def test_token_endpoint_errors_are_translated():
    redirect = f"http://127.0.0.1:{free_port()}/callback"
    bad = token_client(400, {"error": "invalid_client", "error_description": "Invalid client"})
    with pytest.raises(L.LoginError, match="client ID"):
        run(redirect, open_browser=browser(redirect), http=bad)


# ---- Api-level behaviour -------------------------------------------------

def test_save_client_id_validates_and_writes_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# keep me\nSPOTIFY_CLIENT_ID=\nLASTFM_API_KEY=abc\n")
    monkeypatch.setattr(config, "ENV_PATH", env)
    real = config.save_env_value
    monkeypatch.setattr(config, "save_env_value", lambda k, v, path=env: real(k, v, path))
    api = Api(Config())
    assert api.save_client_id("not a client id")["ok"] is False
    r = api.save_client_id("73d1900818c24bc79d0a1b7251af6372")
    assert r["ok"] is True and r["state"]["status"] in (SETUP_REQUIRED, LOGGED_OUT, "connecting")
    text = env.read_text()
    assert "SPOTIFY_CLIENT_ID=73d1900818c24bc79d0a1b7251af6372" in text and "# keep me" in text and "LASTFM_API_KEY=abc" in text
    assert text.count("SPOTIFY_CLIENT_ID") == 1


def test_save_env_value_creates_file(tmp_path):
    p = tmp_path / ".env"
    config.save_env_value("K", "v", p)
    assert p.read_text() == "K=v\n"


def test_login_failure_pushes_message_and_returns_error(monkeypatch):
    from unittest.mock import MagicMock
    api = Api(Config(spotify_client_id="a" * 32)); pushed = []
    api._attach(pushed.append)
    api._auth = MagicMock(); api._auth.login.side_effect = L.LoginError("Port 8888 is already in use")
    r = api.login()
    assert r == {"ok": False, "error": "Port 8888 is already in use"}
    assert pushed[-1]["status"] == LOGGED_OUT and "8888" in pushed[-1]["message"]


def test_login_pushes_the_link_while_waiting():
    from unittest.mock import MagicMock
    api = Api(Config(spotify_client_id="a" * 32)); pushed = []
    api._attach(pushed.append); api._auth = MagicMock(); api._start = MagicMock()
    api._auth.login.side_effect = lambda on_url, cancel: on_url("https://accounts.spotify.com/authorize?x=1")
    assert api.login()["ok"] is True
    assert pushed[0]["status"] == WAITING and pushed[0]["message"].startswith("https://accounts.spotify.com")


def test_poll_403_explains_development_mode():
    from spotipy import SpotifyException
    api = Api(Config()); pushed = []; api._attach(pushed.append)
    api._poll_failed(SpotifyException(403, -1, "x"), 1)
    assert pushed[0]["status"] == ERROR and "User Management" in pushed[0]["message"]


def test_poll_401_signs_out():
    from unittest.mock import MagicMock
    from spotipy import SpotifyException
    api = Api(Config()); pushed = []; api._attach(pushed.append); api._auth = MagicMock()
    api._poll_failed(SpotifyException(401, -1, "x"), 1)
    assert pushed[0]["status"] == LOGGED_OUT and api._auth.logout.called


def test_one_network_blip_is_silent_but_repeated_failures_show_an_error():
    import requests
    api = Api(Config()); pushed = []; api._attach(pushed.append)
    api._poll_failed(requests.exceptions.ConnectionError(), 1)
    assert pushed == []
    api._poll_failed(requests.exceptions.ConnectionError(), 2)
    assert pushed[0]["status"] == ERROR and "internet" in pushed[0]["message"]
