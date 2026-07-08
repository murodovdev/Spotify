# Architecture

TrackFlow is a single-process asyncio application. One event loop runs both the
Telegram long-polling client and an `aiohttp` web server (for the Spotify OAuth
callback and health check).

## Process model

`bot/main.py` is the entry point. On startup it:

1. Configures structured logging (JSON on Railway, human-readable locally).
2. Initializes the SQLite database and loads admin/settings caches.
3. Sweeps orphaned temp files left by a previous crash or deploy.
4. Starts the `aiohttp` server (`/callback`, `/health`).
5. Registers a `UserMiddleware` that upserts the user, resolves their language,
   and enforces bans and maintenance mode before any handler runs.
6. Includes all routers (admin routers first so their FSM states take priority)
   and starts polling.
7. Runs a background maintenance loop and handles graceful shutdown on
   `SIGTERM` / `SIGINT`.

## Layers

```
Telegram ──► handlers/ ──► services/ ──► db/
                 │                        ▲
                 └────► web/oauth.py ─────┘   (Spotify OAuth callback)
```

### `handlers/`
Thin Telegram update handlers, one router per feature area (`links`, `search`,
`youtube`, `video`, `recognize`, `library`, `favorites`, `playlist`,
`settings`, `post_download`, `start`). They parse input and delegate to
services.

### `services/`
The core logic, independent of the Telegram layer:

- **`spotify.py`** — async Spotify Web API client: metadata, OAuth, Liked Songs,
  with automatic embed-mode fallback.
- **`search_engine.py`** / **`matcher.py`** — turn a query or Spotify track into
  the best-matching YouTube source.
- **`downloader.py`** — `yt-dlp` → MP3 transcode → ID3 tags + embedded cover art.
- **`queue.py`** — the download orchestrator: `file_id` cache lookups, bounded
  parallelism (`MAX_DOWNLOADS`), progress updates, and cancellation.
- **`recognizer.py`** — Shazam-based recognition for audio/voice/video clips.
- **`recommender.py`** — "similar songs" from ListenBrainz, Deezer, local audio
  analysis, and optional Last.fm signals.
- **`video_dl.py`** — social-media video downloads.
- **`audio_analysis.py`** / **`audio_effects.py`** — feature extraction and
  effects.
- **`ytdlp_common.py`** — shared `yt-dlp` options, including cookie injection.
- **`tempsweep.py`** — background cleanup of temporary files.
- **`media/`** — the boundary for all heavy media work (`MediaBackend`). Today
  `LocalBackend` runs `yt-dlp`/`ffmpeg` in-process; a remote backend will run
  them on a dedicated VPS. See [HYBRID_MIGRATION.md](HYBRID_MIGRATION.md).
  Handlers must never call `downloader`/`video_dl` download functions directly —
  such a call would stay on Railway when processing moves off-box.

### `db/`
SQLite via `aiosqlite`. Stores users, the Telegram `file_id` cache, download
history, and encrypted OAuth tokens. `maintenance.py` runs periodic upkeep;
`repo.py` batches writes and flushes on shutdown.

### `admin/`
A self-contained admin control panel: role management, bans, broadcasts,
maintenance mode, an in-memory log buffer surfaced in the UI, and usage
dashboards. All admin handlers are guarded by an `AdminFilter`.

### `web/`
`oauth.py` serves the Spotify OAuth callback (exchanging the auth code for
tokens) and the `/health` endpoint used by the platform health check.

## Key design decisions

- **`file_id` caching.** Once a track is uploaded to Telegram, its `file_id` is
  stored and reused, so repeat requests skip download and transcode entirely.
- **Embed-mode fallback.** The bot degrades gracefully when Spotify credentials
  are missing or the app owner lacks Premium (see
  [CONFIGURATION.md](CONFIGURATION.md)).
- **Single replica.** Long-polling and the attached volume both require exactly
  one instance; horizontal scaling is intentionally not supported.
- **Encryption at rest.** OAuth tokens are stored Fernet-encrypted.
