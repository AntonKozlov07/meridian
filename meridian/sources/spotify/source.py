"""PlayerSource backed by the Spotify Web API (spotipy)."""
from __future__ import annotations

import time
from collections import Counter

import spotipy

from meridian.core.state import NO_DEVICE, READY, Device, PlayerState, Track
from meridian.core.timeline import build_timeline

PAST_COUNT = 4  # past blocks shown left of the now line
QUEUE_REFRESH_S = 30  # the queue is re-read this often, and on every track change
MAX_SKIPS = 8  # beyond this, jump with start_playback instead of repeated next

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
        self._past: list[Track] = []
        self._queue: list[Track] = []
        self._queue_at = 0.0
        self._timeline_for: str | None = None  # track id the past/queue caches belong to
        self._past_stale = False
        self._mine: Counter[str] = Counter()  # uris queued from Meridian, not yet played
        self._context_uri: str | None = None

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
        self._context_uri = (pb.get("context") or {}).get("uri")
        self._refresh_timeline_data(track)
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
            timeline=self._timeline(track, int(pb.get("progress_ms") or 0), bool(pb.get("is_playing"))),
        )

    # -- timeline ------------------------------------------------------
    def _refresh_timeline_data(self, track: Track) -> None:
        changed = track.id != self._timeline_for
        if changed:
            # a track we queued has started: it is no longer waiting in the queue
            if self._mine[track.uri] > 0:
                self._mine[track.uri] -= 1
        if changed or self._past_stale:
            self._past = self._read_past(track)
            self._past_stale = False
        if changed or time.monotonic() - self._queue_at > QUEUE_REFRESH_S:
            self._queue = self._read_queue()
            self._queue_at = time.monotonic()
        self._timeline_for = track.id

    def _read_past(self, current: Track) -> list[Track]:
        try:
            items = self._sp.current_user_recently_played(limit=20).get("items", [])
        except spotipy.SpotifyException:
            return self._past
        seen: set[str] = {current.id}
        recent: list[Track] = []  # newest first
        for it in items:
            t = it.get("track")
            if not t or t.get("id") in seen:
                continue
            seen.add(t["id"])
            recent.append(parse_track(t))
            if len(recent) == PAST_COUNT:
                break
        return list(reversed(recent))

    def _read_queue(self) -> list[Track]:
        try:
            q = self._sp.queue().get("queue", [])
        except spotipy.SpotifyException:
            return self._queue
        return [parse_track(t) for t in q if t]

    def invalidate_queue(self) -> None:
        self._queue_at = 0.0
        self._past_stale = True  # history changes on skip

    def _timeline(self, track: Track, progress_ms: int, is_playing: bool):
        # Spotify does not say which queue items the user added. Items queued from
        # Meridian are marked; everything else is treated as coming from the context.
        waiting = Counter(self._mine)
        upcoming = []
        for t in self._queue:
            mine = waiting[t.uri] > 0
            if mine:
                waiting[t.uri] -= 1
            upcoming.append((t, mine))
        return build_timeline(track, progress_ms, _now_ms(), self._past, upcoming, is_playing)

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
        self.invalidate_queue()

    def previous(self) -> None:
        self._sp.previous_track()
        self.invalidate_queue()

    def add_to_queue(self, uri: str) -> None:
        self._sp.add_to_queue(uri)
        self._mine[uri] += 1
        self._queue_at = 0.0

    def play_track(self, uri: str) -> None:
        """Play a specific track, staying in the current playlist or album when it is part of it."""
        if self._context_uri:
            try:
                self._sp.start_playback(context_uri=self._context_uri, offset={"uri": uri})
                self.invalidate_queue()
                return
            except spotipy.SpotifyException:
                pass  # not in that context (e.g. a queued song): play it on its own
        self._sp.start_playback(uris=[uri])
        self.invalidate_queue()

    def jump_ahead(self, steps: int, uri: str) -> None:
        """Skip forward `steps` tracks so queued songs keep their place; far jumps replay by uri."""
        if steps < 1:
            return
        if steps > MAX_SKIPS:
            self.play_track(uri)
            return
        for _ in range(steps):
            self._sp.next_track()
            time.sleep(0.25)  # Spotify drops skips that arrive too quickly
        self.invalidate_queue()

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
