"""Checks everything sign-in depends on and says what to fix.  Run: python -m meridian.doctor [--login]"""
from __future__ import annotations

import re
import socket
import sys

import httpx

from meridian import config
from meridian.sources.spotify import auth as auth_mod
from meridian.sources.spotify.login import LoginError, parse_redirect


def check(ok: bool, good: str, bad: str) -> bool:
    print(("  ok    " if ok else "  FAIL  ") + (good if ok else bad))
    return ok


def main(argv: list[str]) -> int:
    cfg = config.load()
    print(f"Python {sys.version.split()[0]}   project folder: {config.ROOT}")
    results = []

    print("\nConfiguration")
    results.append(check(config.ENV_PATH.exists(), f".env found at {config.ENV_PATH}",
                         f".env not found at {config.ENV_PATH}. Copy .env.example to .env in that folder."))
    cid = cfg.spotify_client_id
    results.append(check(bool(re.fullmatch(r"[0-9a-fA-F]{32}", cid)), f"client ID set ({cid[:4]}...{cid[-4:]})",
                         "SPOTIFY_CLIENT_ID is empty or not 32 letters/numbers. Put it in .env as SPOTIFY_CLIENT_ID=<id> "
                         "(a line inside the file, not typed into the terminal), or paste it into the app's setup screen."))
    port = None
    try:
        host, port, path = parse_redirect(cfg.spotify_redirect_uri)
        results.append(check(True, f"redirect URI {cfg.spotify_redirect_uri} is valid", ""))
    except LoginError as e:
        results.append(check(False, "", str(e)))
    print(f"        Your Spotify app must list exactly: {cfg.spotify_redirect_uri}  (dashboard > your app > Settings > Redirect URIs > Save)")

    print("\nThis computer")
    if port:
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port))
            results.append(check(True, f"port {port} is free", ""))
        except OSError as e:
            results.append(check(False, "", f"port {port} is busy ({e.strerror}). Close what is using it or change the port."))
        finally:
            s.close()
    try:
        r = httpx.get("https://accounts.spotify.com", timeout=8, follow_redirects=True)
        results.append(check(r.status_code < 500, "can reach accounts.spotify.com", f"Spotify answered {r.status_code}"))
    except httpx.HTTPError as e:
        results.append(check(False, "", f"cannot reach accounts.spotify.com ({type(e).__name__}). Check internet, VPN or proxy."))
    try:
        import keyring
        keyring.set_password("meridian-doctor", "probe", "x")
        ok = keyring.get_password("meridian-doctor", "probe") == "x"
        keyring.delete_password("meridian-doctor", "probe")
        results.append(check(ok, f"keychain works ({type(keyring.get_keyring()).__name__})", "keychain read-back failed"))
    except Exception as e:
        check(False, "", f"keychain unavailable ({type(e).__name__}). Sign-in still works but must be repeated each launch.")

    if "--login" in argv:
        if not all(results):
            print("\nFix the failures above, then run with --login again.")
            return 1
        print("\nSigning in. A browser tab opens; approve Meridian there.")
        a = auth_mod.SpotifyAuth(cid, cfg.spotify_redirect_uri)
        try:
            a.login(on_url=lambda u: print(f"If no tab opened, open this link:\n{u}\n"))
            me = a.client().current_user()
        except LoginError as e:
            print(f"\nSign-in failed: {e}")
            return 1
        except Exception as e:
            print(f"\nSigned in, but Spotify refused the next request: {e}")
            print("If this says 403 or 'user not registered', add your Spotify email under User Management in the dashboard.")
            return 1
        print(f"\nSigned in as {me.get('display_name') or me.get('id')}. Now run: python -m meridian.main")
        return 0

    print("\nAll checks passed. Run with --login to test signing in from the terminal."
          if all(results) else "\nFix the FAIL lines above, then run this again.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
