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
