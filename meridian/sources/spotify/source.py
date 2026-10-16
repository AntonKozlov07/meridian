"""PlayerSource backed by the Spotify Web API (spotipy)."""
from __future__ import annotations

import time

import spotipy

from meridian.core.state import NO_DEVICE, READY, Device, PlayerState, Track

REPEAT_MODES = ("off", "context", "track")


def parse_track(item: dict) -> Track:
    album = item.get("album") or {}
    images = album.get("images") or (item.get("images") or [])
    release = album.get("release_date") or ""
    if item.get("type") == "episode":  # podcasts: show name stands in for artist/album
        show = item.get("show") or {}
        artist, album_name = show.get("publisher") or show.get("name") or "", show.get("name") or ""
        images = images or show.get("images") or []
        release = item.get("release_date") or ""
    else:
        artist = ", ".join(a["name"] for a in item.get("artists", []))
        album_name = album.get("name", "")
    year = int(release[:4]) if release[:4].isdigit() else None
    return Track(
        id=item.get("id") or item.get("uri", ""),
        uri=item.get("uri", ""),
        title=item.get("name", ""),
        artist=artist,
        album=album_name,
        year=year,
        duration_ms=int(item.get("duration_ms") or 0),
        art_url=images[0]["url"] if images else None,
        is_playable=item.get("is_playable", True),
        isrc=(item.get("external_ids") or {}).get("isrc"),
        track_number=item.get("track_number"),
        album_tracks=album.get("total_tracks"),
    )


def parse_device(d: dict) -> Device:
    vol = d.get("volume_percent")
    return Device(
        id=d.get("id") or "",
        name=d.get("name", ""),
        type=d.get("type", ""),
        is_active=bool(d.get("is_active")),
        is_restricted=bool(d.get("is_restricted")),
        volume=None if vol is None else vol / 100,
    )


class SpotifySource:
    def __init__(self, sp: spotipy.Spotify):
        self._sp = sp
        self._context_names: dict[str, str | None] = {}
        self._liked: dict[str, bool] = {}

    # -- state ---------------------------------------------------------
    def poll(self) -> PlayerState:
        pb = self._sp.current_playback(additional_types="track,episode")
        devices = self.devices()
        item = pb.get("item") if pb else None
        if not pb or not item:
            return PlayerState(status=NO_DEVICE, devices=devices, fetched_at_ms=_now_ms(),
                               is_playing=bool(pb and pb.get("is_playing")),
                               message=None if pb is None else "Nothing is loaded on the active device.")
        track = parse_track(item)
        device = pb.get("device") or {}
        vol = device.get("volume_percent")
        return PlayerState(
            status=READY,
            track=track,
            is_playing=bool(pb.get("is_playing")),
            progress_ms=int(pb.get("progress_ms") or 0),
            fetched_at_ms=_now_ms(),
            shuffle=bool(pb.get("shuffle_state")),
            repeat=pb.get("repeat_state") or "off",
            volume=None if vol is None else vol / 100,
            context_name=self._context_name(pb.get("context")),
            liked=self._is_liked(track) if item.get("type") != "episode" else False,
            devices=devices,
        )

    def _context_name(self, ctx: dict | None) -> str | None:
        if not ctx:
            return None
        uri = ctx.get("uri", "")
        if uri not in self._context_names:
            try:
                kind, cid = ctx["type"], uri.split(":")[-1]
                if kind == "playlist":
                    name = self._sp.playlist(cid, fields="name")["name"]
                elif kind == "album":
                    name = self._sp.album(cid)["name"]
                elif kind == "artist":
                    name = self._sp.artist(cid)["name"]
                else:
                    name = None
            except spotipy.SpotifyException:
                name = None  # e.g. Spotify-owned playlists that are not readable; don't retry every poll
            self._context_names[uri] = name
        return self._context_names[uri]

    def _is_liked(self, track: Track) -> bool:
        if track.id not in self._liked:
            try:
                self._liked[track.id] = bool(self._sp.current_user_saved_tracks_contains([track.id])[0])
            except spotipy.SpotifyException:
                return False
        return self._liked[track.id]

    # -- controls ------------------------------------------------------
    def play(self) -> None:
        self._sp.start_playback()

    def pause(self) -> None:
        self._sp.pause_playback()

    def next(self) -> None:
        self._sp.next_track()

    def previous(self) -> None:
        self._sp.previous_track()

    def seek(self, position_ms: int) -> None:
        self._sp.seek_track(max(0, int(position_ms)))

    def set_volume(self, percent: int) -> None:
        self._sp.volume(max(0, min(100, int(percent))))

    def set_shuffle(self, on: bool) -> None:
        self._sp.shuffle(bool(on))

    def set_repeat(self, mode: str) -> None:
        if mode not in REPEAT_MODES:
            raise ValueError(f"bad repeat mode: {mode}")
        self._sp.repeat(mode)

    def devices(self) -> list[Device]:
        return [parse_device(d) for d in self._sp.devices().get("devices", [])]

    def transfer(self, device_id: str) -> None:
        self._sp.transfer_playback(device_id, force_play=True)

    def set_saved(self, track_id: str, saved: bool) -> None:
        (self._sp.current_user_saved_tracks_add if saved else self._sp.current_user_saved_tracks_delete)([track_id])
        self._liked[track_id] = saved


def _now_ms() -> int:
    return int(time.time() * 1000)
