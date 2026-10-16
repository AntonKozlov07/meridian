"""Plain data the UI renders. Everything here is JSON-serialisable via to_dict()."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# status values: what the UI shows instead of the player
SETUP_REQUIRED = "setup_required"  # no client id configured
WAITING = "waiting"  # browser sign-in in progress; message holds the link
ERROR = "error"  # signed in but Spotify is refusing or unreachable; message says why
CONNECTING = "connecting"  # session found, first poll not back yet
LOGGED_OUT = "logged_out"
NO_DEVICE = "no_device"
READY = "ready"


@dataclass
class Track:
    id: str
    uri: str
    title: str
    artist: str
    album: str
    year: int | None
    duration_ms: int
    art_url: str | None
    is_playable: bool = True
    isrc: str | None = None
    track_number: int | None = None
    album_tracks: int | None = None
    artists: list[str] = field(default_factory=list)  # individual artist names; `artist` is them joined


@dataclass
class CatalogItem:
    """A playlist, album, artist or the Liked Songs collection: anything that can be played as a context."""
    kind: str  # playlist | album | artist | liked
    id: str
    uri: str
    name: str
    subtitle: str
    art_url: str | None = None


@dataclass
class Library:
    playlists: list[CatalogItem] = field(default_factory=list)  # Liked Songs first
    albums: list[CatalogItem] = field(default_factory=list)
    artists: list[CatalogItem] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)  # sections Spotify would not return


@dataclass
class SearchResults:
    query: str = ""
    songs: list[Track] = field(default_factory=list)
    collections: list[CatalogItem] = field(default_factory=list)


@dataclass
class Device:
    id: str
    name: str
    type: str
    is_active: bool
    is_restricted: bool = False
    volume: float | None = None  # 0..1


@dataclass
class PlayerState:
    status: str = LOGGED_OUT
    track: Track | None = None
    is_playing: bool = False
    progress_ms: int = 0
    fetched_at_ms: int = 0  # wall clock when progress_ms was read; the UI interpolates from it
    shuffle: bool = False
    repeat: str = "off"  # off | context | track
    volume: float | None = None
    context_name: str | None = None
    liked: bool = False
    devices: list[Device] = field(default_factory=list)
    timeline: "Timeline | None" = None
    message: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


from meridian.core.timeline import Timeline  # noqa: E402  (after Track, which timeline imports)
