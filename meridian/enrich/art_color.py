"""Two ambient colours from album art, for the wash across the top of the canvas."""
from __future__ import annotations

import colorsys
import io

import httpx
from colorthief import ColorThief

from meridian.enrich.common import Transient


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _score(rgb) -> float:
    """Prefer colours with real saturation and mid lightness: they read as colour on both themes."""
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    return s * (1 - abs(l - 0.5) * 1.6)


def _distance(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def pick_two(palette: list[tuple[int, int, int]]) -> list[str] | None:
    if not palette:
        return None
    ranked = sorted(palette, key=_score, reverse=True)
    first = ranked[0]
    second = next((c for c in ranked[1:] if _distance(c, first) > 70), None)
    if second is None:  # a near-monochrome cover: lighten the first colour for the second wash
        h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in first))
        second = tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, min(1, l + 0.18), s))
    return [_hex(first), _hex(second)]


def colors_from_image(data: bytes) -> list[str] | None:
    try:
        return pick_two(ColorThief(io.BytesIO(data)).get_palette(color_count=6, quality=5))
    except Exception:  # unreadable image, or too few colours for the quantiser
        return None


def fetch_colors(client: httpx.Client, art_url: str) -> list[str] | None:
    """Downloads the art and extracts two colours. None for an unreadable image. Raises Transient."""
    try:
        r = client.get(art_url)
    except httpx.HTTPError as e:
        raise Transient(type(e).__name__) from e
    if r.status_code >= 500 or r.status_code == 429:
        raise Transient(f"HTTP {r.status_code}")
    if r.status_code != 200:
        return None
    return colors_from_image(r.content)
