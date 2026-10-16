# Meridian

Desktop music player on top of Spotify. See the handoff docs for the design and build order.

## Run (step 3: live Spotify)

1. `pip install -r requirements.txt`
2. In the Spotify developer dashboard create an app, add redirect URI `http://127.0.0.1:8888/callback`.
3. `cp .env.example .env` and set `SPOTIFY_CLIENT_ID`.
4. Start Spotify on this computer, a phone or a speaker (playback control needs Premium).
5. `python -m meridian.main`. If no client ID is set the app asks for it on screen and saves it to `.env`. Then press "Connect Spotify".

Tokens are stored in the OS keychain. Tests: `python -m pytest`.

## Timeline (step 4)

The strip shows up to 4 recently played songs, the current song and the queue, laid out on the wall clock by `meridian/core/timeline.py`.
Click an upcoming block to skip forward to it (queued songs keep their place), or a past block to replay it.

Spotify's API does not say which queue items you added. Songs queued from inside Meridian get the "Queued" tag; songs
queued from other Spotify apps appear as normal upcoming songs.

## Can't sign in?

Run `python -m meridian.doctor`. It checks `.env`, the client ID, the redirect URI, the port, your connection and the keychain,
and says what to fix. `python -m meridian.doctor --login` tries the sign-in from the terminal and prints the exact error.
The app also writes a log to `~/.meridian/meridian.log`.

Common causes:
- **Redirect URI** must be listed exactly as `http://127.0.0.1:8888/callback` in the Spotify dashboard (Settings > Redirect URIs > Save). `localhost` is rejected.
- **Development mode:** until you request extended access, only accounts added under *User Management* in the dashboard can use your app. Add your Spotify email there.
- **Port 8888 busy:** close the other program, or change the port in `SPOTIFY_REDIRECT_URI` and in the dashboard.

## Library and search (step 5)

- **Library:** Liked Songs, your playlists, saved albums and followed artists, with All / Playlists / Albums / Artists filters. Click a card to play it.
- **Command bar** (`Ctrl+K`, `Cmd+K` or `/`): searches Spotify for songs, playlists, albums and artists. Enter plays, Shift+Enter adds a song to the queue.
  Lyric-line search arrives with lyrics in step 6.
- The library is cached for 5 minutes and refreshes when you open it.

## Lyrics, credits and stats (step 6)

Each source fills in on its own after a song starts, in the background, and is cached in `~/.meridian/cache.db`.
A source that has nothing, or is down, only leaves its own chip or panel empty.

| What | Source | Needs |
| --- | --- | --- |
| Synced lyrics, click a line to seek | LRCLIB | nothing |
| Credits (performers, writers, producers, engineers) | MusicBrainz | nothing. Set `MUSICBRAINZ_USER_AGENT` with your email in `.env` |
| BPM, key, energy | ReccoBeats, then GetSongBPM for gaps | GetSongBPM needs `GETSONGBPM_API_KEY` (it asks for a backlink, shown in About) |
| Listeners, your plays, scrobbling | Last.fm | `LASTFM_API_KEY` and `LASTFM_API_SECRET`, then "Link Last.fm" in the About tab |
| Ambient colour wash | the album art, extracted on your computer | nothing |

Command bar: typing a line from a song's lyrics finds it, if that song's lyrics are already cached (you have played it before).
Enter plays it from that line.

Once Last.fm is linked, Meridian scrobbles what you play (Last.fm's rule: over 30s, and half the song or 4 minutes). Unlink in About to stop.
