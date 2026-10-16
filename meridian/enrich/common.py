"""Shared pieces for the enrichment sources."""
from __future__ import annotations

import httpx


class Transient(Exception):
    """A temporary failure (rate limit, outage, no network). Never cached as a miss."""


def get_json(client: httpx.Client, url: str, params: dict | None = None, headers: dict | None = None):
    """GET returning parsed JSON; None on 404; Transient on anything that may succeed later."""
    try:
        r = client.get(url, params=params, headers=headers)
    except httpx.HTTPError as e:
        raise Transient(f"{type(e).__name__}") from e
    if r.status_code == 404:
        return None
    if r.status_code == 429 or r.status_code >= 500:
        raise Transient(f"HTTP {r.status_code}")
    if r.status_code != 200:
        return None  # 400s other than 404/429: the request itself is unanswerable, so a miss
    try:
        return r.json()
    except ValueError as e:
        raise Transient("bad JSON") from e


def user_agent(configured: str) -> str:
    return configured or "Meridian/0.1 (contact not set)"
