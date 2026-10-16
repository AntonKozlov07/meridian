"""Loads local configuration from .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = Path(__file__).resolve().parent / "ui"

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Config:
    spotify_client_id: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"
    getsongbpm_api_key: str = ""
    lastfm_api_key: str = ""
    lastfm_api_secret: str = ""
    musicbrainz_user_agent: str = "Meridian/0.1 (contact not set)"


def load() -> Config:
    g = os.environ.get
    return Config(
        spotify_client_id=g("SPOTIFY_CLIENT_ID", ""),
        spotify_redirect_uri=g("SPOTIFY_REDIRECT_URI", Config.spotify_redirect_uri),
        getsongbpm_api_key=g("GETSONGBPM_API_KEY", ""),
        lastfm_api_key=g("LASTFM_API_KEY", ""),
        lastfm_api_secret=g("LASTFM_API_SECRET", ""),
        musicbrainz_user_agent=g("MUSICBRAINZ_USER_AGENT", Config.musicbrainz_user_agent),
    )
