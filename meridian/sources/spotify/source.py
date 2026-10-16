"""PlayerSource backed by the Spotify Web API (spotipy)."""
from __future__ import annotations

import time
from collections import Counter

import spotipy

from meridian.core.state import NO_DEVICE, READY, CatalogItem, Device, Library, PlayerState, SearchResults, Track
from meridian.core.timeline import build_timeline

PAST_COUNT = 4  # past blocks shown left of the now line
QUEUE_REFRESH_S = 30  # the queue is re-read this often, and on every track change
LIBRARY_TTL_S = 300
LIBRARY_CAP = 200  # per section
SEARCH_LIMIT = 5  # per type
MAX_SKIPS = 8  # beyond this, jump with start_playback instead of repeated next
NEVER = float("-inf")  # "not fetched yet" for time.monotonic() stamps (0.0 would depend on system uptime)

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
        artists=[x["name"] for x in item.get("artists", [])] or ([artist] if artist else []),
    )


def _art(images: list | None) -> str | None:
    return images[0]["url"] if images else None


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}" + ("" if n == 1 else "s")


def parse_playlist(p: dict) -> CatalogItem:
    tracks = p.get("tracks") or p.get("items") or {}
    n = tracks.get("total") if isinstance(tracks, dict) else None
    owner = (p.get("owner") or {}).get("display_name")
    sub = "Playlist" + (f" · {_plural(n, 'song')}" if n is not None else (f" · {owner}" if owner else ""))
    return CatalogItem("playlist", p["id"], p["uri"], p.get("name", ""), sub, _art(p.get("images")))


def parse_album(a: dict) -> CatalogItem:
    who = ", ".join(x["name"] for x in a.get("artists", []))
    return CatalogItem("album", a["id"], a["uri"], a.get("name", ""), "Album" + (f" · {who}" if who else ""),
                       _art(a.get("images")))


def parse_artist(a: dict) -> CatalogItem:
    return CatalogItem("artist", a["id"], a["uri"], a.get("name", ""), "Artist", _art(a.get("images")))


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
        self._queue_at = NEVER
        self._timeline_for: str | None = None  # track id the past/queue caches belong to
        self._past_stale = False
        self._mine: Counter[str] = Counter()  # uris queued from Meridian, not yet played
        self._context_uri: str | None = None
        self._device_id: str | None = None  # the device Spotify reported active at the last poll
        self._last_device_id: str | None = None  # the last one that was ever active: where to resume
        self._library: Library | None = None
        self._library_at = NEVER
        self._user_id: str | None = None
        self._user_name: str | None = None

    # -- state ---------------------------------------------------------
    def poll(self) -> PlayerState:
        pb = self._sp.current_playback(additional_types="track,episode", market="from_token")  # market makes is_playable appear
        devices = self.devices()
        item = pb.get("item") if pb else None
        if not pb or not item:
            self._device_id = (pb or {}).get("device", {}).get("id") if pb else None
            return PlayerState(status=NO_DEVICE, devices=devices, fetched_at_ms=_now_ms(),
                               is_playing=bool(pb and pb.get("is_playing")),
                               message=None if pb is None else "Nothing is loaded on the active device.")
        track = parse_track(item)
        self._context_uri = (pb.get("context") or {}).get("uri")
        self._device_id = (pb.get("device") or {}).get("id")
        self._last_device_id = self._device_id or self._last_device_id
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
            user_name=self._display_name(),
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
        self._queue_at = NEVER
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

    # -- library and search --------------------------------------------
    def library(self, force: bool = False) -> Library:
        """Playlists, saved albums, followed artists. Cached for a few minutes; a failing section is reported, not fatal."""
        if self._library and not force and time.monotonic() - self._library_at < LIBRARY_TTL_S:
            return self._library
        lib = Library()
        sp = self._sp
        try:
            uid = self._user()
            total = sp.current_user_saved_tracks(limit=1).get("total", 0)
            lib.playlists.append(CatalogItem("liked", "liked", f"spotify:user:{uid}:collection", "Liked Songs",
                                             f"Playlist · {_plural(total, 'song')}", None))
        except spotipy.SpotifyException:
            lib.failed.append("liked songs")
        lib.playlists += self._section("playlists", lib, lambda off: sp.current_user_playlists(limit=50, offset=off),
                                       lambda r: r, parse_playlist)
        lib.albums = self._section("albums", lib, lambda off: sp.current_user_saved_albums(limit=50, offset=off),
                                   lambda r: r, lambda it: parse_album(it["album"]))
        lib.artists = self._artists(lib)
        self._library, self._library_at = lib, time.monotonic()
        return lib

    @staticmethod
    def _section(name, lib, fetch, unwrap, parse) -> list[CatalogItem]:
        out: list[CatalogItem] = []
        try:
            while len(out) < LIBRARY_CAP:
                page = unwrap(fetch(len(out)))
                items = [i for i in page.get("items", []) if i]  # Spotify returns null for deleted entries
                if not items:
                    break
                out += [parse(i) for i in items]
                if not page.get("next"):
                    break
        except spotipy.SpotifyException:
            lib.failed.append(name)
        return out

    def _artists(self, lib: Library) -> list[CatalogItem]:
        out, after = [], None
        try:
            while len(out) < LIBRARY_CAP:
                page = self._sp.current_user_followed_artists(limit=50, after=after).get("artists", {})
                items = [i for i in page.get("items", []) if i]
                out += [parse_artist(i) for i in items]
                after = (page.get("cursors") or {}).get("after")
                if not items or not after:
                    break
        except spotipy.SpotifyException:
            lib.failed.append("artists")
        return out

    def _display_name(self) -> str | None:
        if self._user_name is None:
            try:
                me = self._sp.current_user()
                self._user_id, self._user_name = me["id"], me.get("display_name") or me["id"]
            except (spotipy.SpotifyException, KeyError, TypeError):
                return None
        return self._user_name

    def _user(self) -> str:
        if not self._user_id:
            self._user_id = self._sp.current_user()["id"]
        return self._user_id

    def search(self, query: str) -> SearchResults:
        q = (query or "").strip()
        if not q:
            return SearchResults()
        r = self._sp.search(q=q, type="track,playlist,album,artist", limit=SEARCH_LIMIT, market="from_token")
        songs = [parse_track(t) for t in (r.get("tracks") or {}).get("items", []) if t]
        songs = [t for t in songs if t.is_playable]
        cols = [parse_playlist(p) for p in (r.get("playlists") or {}).get("items", []) if p]
        cols += [parse_album(a) for a in (r.get("albums") or {}).get("items", []) if a]
        cols += [parse_artist(a) for a in (r.get("artists") or {}).get("items", []) if a]
        return SearchResults(query=q, songs=songs, collections=cols)

    def _start(self, **kw) -> None:
        """start_playback aimed at a specific device, never at "whatever Spotify picks".

        Without a device_id Spotify chooses, and when the phone has dropped out as the active device
        the request lands nowhere or on the wrong device. If the target no longer answers, wake the last
        device we used (or the first controllable one) instead of giving up.
        """
        target = self._device_id or self._last_device_id
        try:
            self._sp.start_playback(device_id=target, **kw) if target else self._sp.start_playback(**kw)
        except spotipy.SpotifyException as e:
            if not _device_gone(e):
                raise
            devices = [d for d in self.devices() if d.id and not d.is_restricted]
            fallback = next((d for d in devices if d.id == self._last_device_id), None) or (devices[0] if devices else None)
            if fallback is None:
                raise
            self._sp.start_playback(device_id=fallback.id, **kw)
            self._device_id = self._last_device_id = fallback.id

    def play_uri(self, uri: str, kind: str) -> None:
        """Play a song on its own, or an album, playlist, artist or Liked Songs from the top."""
        if kind in ("track", "episode"):
            self._start(uris=[uri])
        else:
            self._start(context_uri=uri)
        self.invalidate_queue()

    def play_at(self, uri: str, position_ms: int) -> None:
        """Play a song starting part-way in, e.g. from a lyric-line search hit."""
        self._start(uris=[uri], position_ms=max(0, int(position_ms)))
        self.invalidate_queue()

    # -- controls ------------------------------------------------------
    def play(self) -> None:
        self._start()

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
        self._queue_at = NEVER

    def play_track(self, uri: str) -> None:
        """Play a specific track, staying in the current playlist or album when it is part of it."""
        if self._context_uri:
            try:
                self._start(context_uri=self._context_uri, offset={"uri": uri})
                self.invalidate_queue()
                return
            except spotipy.SpotifyException:
                pass  # not in that context (e.g. a queued song): play it on its own
        self._start(uris=[uri])
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


def _device_gone(e: spotipy.SpotifyException) -> bool:
    """404 NO_ACTIVE_DEVICE / "Device not found": the target went idle. Other 404s (e.g. track not in that playlist) are not this."""
    return e.http_status == 404 and ((getattr(e, "reason", "") or "").upper() == "NO_ACTIVE_DEVICE" or "device not found" in str(e).lower())


def _now_ms() -> int:
    return int(time.time() * 1000)
