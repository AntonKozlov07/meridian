# Meridian

Desktop music player on top of Spotify. See the handoff docs for the design and build order.

## Run (step 3: live Spotify)

1. `pip install -r requirements.txt`
2. In the Spotify developer dashboard create an app, add redirect URI `http://127.0.0.1:8888/callback`.
3. `cp .env.example .env` and set `SPOTIFY_CLIENT_ID`.
4. Start Spotify on this computer, a phone or a speaker (playback control needs Premium).
5. `python -m meridian.main`, then press "Connect Spotify".

Tokens are stored in the OS keychain. Tests: `python -m pytest`.

## Timeline (step 4)

The strip shows up to 4 recently played songs, the current song and the queue, laid out on the wall clock by `meridian/core/timeline.py`.
Click an upcoming block to skip forward to it (queued songs keep their place), or a past block to replay it.

Spotify's API does not say which queue items you added. Songs queued from inside Meridian get the "Queued" tag; songs
queued from other Spotify apps appear as normal upcoming songs.
