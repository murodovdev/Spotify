<div align="center">

# 🎧 TrackFlow

**A fast, multi-source music bot for Telegram.**

Send a Spotify, YouTube, or social-media link — or just type a song name — and
TrackFlow finds the best audio, tags it, and delivers it in seconds.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![Deploy on Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?logo=railway&logoColor=white)](https://railway.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Overview

TrackFlow is a self-hostable Telegram bot that turns links and search queries
into high-quality, fully-tagged audio files. It reads metadata from Spotify,
finds the closest matching source on YouTube (the same approach as `spotdl`),
downloads and transcodes it with `yt-dlp` + FFmpeg, and caches the result so the
next request for the same track is instant.

It also recognizes music from voice/video clips, downloads audio from YouTube and
social-media video links, and ships with a full admin control panel.

> [!NOTE]
> Spotify does not serve audio directly. TrackFlow uses Spotify only for
> metadata (title, artist, album, cover, duration) and sources the audio from
> YouTube Music. Intended for personal use — respect the copyright laws in your
> jurisdiction.

## Features

- 🔗 **Link detection** — paste a Spotify track, album, playlist, or artist link and TrackFlow resolves it automatically.
- 🔍 **Text search** — type a song name; the search engine finds and returns the best match.
- ▶️ **YouTube & video links** — extract audio from YouTube, or download videos from popular social platforms.
- 🎤 **Music recognition** — forward a voice note, audio, or video clip and TrackFlow identifies the track (Shazam-powered).
- ❤️ **Liked Songs** — connect your Spotify account via OAuth and bulk-download your library.
- ⭐ **Favorites, history & playlists** — personal library management inside the chat.
- ⚡ **Instant cache** — Telegram `file_id` caching means a previously downloaded track is re-sent in about a second.
- 🚀 **Parallel downloads** — albums and playlists are processed several tracks at a time.
- 🏷 **Full metadata** — ID3 tags, embedded cover art, and duration on every file.
- 🎚 **Quality control** — choose 128 / 320 kbps, apply audio effects, and edit metadata.
- 🎯 **Recommendations** — a "similar songs" engine built on ListenBrainz, Deezer, local audio analysis, and (optionally) Last.fm.
- 🌍 **Multi-language** — Uzbek, English, and Russian UI.
- 🛡 **Admin panel** — roles, bans, broadcasts, maintenance mode, live logs, and usage dashboards.

## Supported platforms

| Source | Capability |
|---|---|
| Spotify | Track / album / playlist / artist links, text search, Liked Songs (OAuth) |
| YouTube / YouTube Music | Audio extraction from links, primary audio source for search |
| Social video platforms | Video download + "Find Music" recognition |
| Local media | Recognize audio/voice/video clips sent to the bot |

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 (asyncio, `uvloop` on Linux) |
| Bot framework | [aiogram 3](https://docs.aiogram.dev/) |
| Web / OAuth server | [aiohttp](https://docs.aiohttp.org/) |
| Media | [yt-dlp](https://github.com/yt-dlp/yt-dlp) + FFmpeg, [mutagen](https://mutagen.readthedocs.io/) |
| Storage | SQLite via [aiosqlite](https://aiosqlite.omnilib.dev/) |
| Config | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Security | [cryptography](https://cryptography.io/) (Fernet token encryption) |
| Recognition | [shazamio](https://github.com/shazamio/ShazamIO) |
| Analysis | NumPy (audio feature extraction) |
| Deployment | Docker, [Railway](https://railway.app/) |

## Quick start (local)

**Prerequisites:** Python 3.12+, [FFmpeg](https://ffmpeg.org/), and a Telegram bot
token from [@BotFather](https://t.me/BotFather).

```bash
# 1. Install FFmpeg
#    Windows:  winget install ffmpeg
#    macOS:    brew install ffmpeg
#    Debian:   sudo apt install ffmpeg

# 2. Clone and enter the project
git clone https://github.com/murodovdev/Spotify.git trackflow
cd trackflow

# 3. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env             # Windows: copy .env.example .env
#    Edit .env and set BOT_TOKEN (Spotify keys are optional — see below)

# 5. Run
python -m bot.main
```

The bot starts polling immediately and launches a local OAuth server on
`http://127.0.0.1:8080` (used only for the Spotify "Connect account" flow).

## Environment variables

Only `BOT_TOKEN` is required. Spotify credentials unlock link resolution and
Liked Songs; without them the bot automatically falls back to **embed mode**
(metadata from public `open.spotify.com/embed` pages, YouTube-based search).

| Variable | Required | Description |
|---|:---:|---|
| `BOT_TOKEN` | ✅ | Telegram bot token from @BotFather. |
| `SPOTIFY_CLIENT_ID` | | Spotify app client ID (enables full API + Liked Songs). |
| `SPOTIFY_CLIENT_SECRET` | | Spotify app client secret. |
| `SPOTIFY_REDIRECT_URI` | | OAuth callback. Auto-derived if left blank. |
| `ADMIN_ID` | | Telegram user ID granted owner/admin access. |
| `ENCRYPTION_KEY` | | Fernet key for encrypting stored tokens. Derived from `BOT_TOKEN` if blank. |
| `DB_PATH` | | SQLite path. Auto: `/data/bot.db` on Railway, `data/bot.db` locally. |
| `PORT` | | OAuth web server port (default `8080`). |
| `MAX_DOWNLOADS` | | Max concurrent downloads (default `4`). |
| `LASTFM_API_KEY` | | Optional — strengthens the recommendation engine. |
| `TS_AUTHKEY` / `TS_EXIT_NODE` | | Route YouTube out via a home Tailscale exit node — the cookieless fix for bot checks. See [Configuration](docs/CONFIGURATION.md). |
| `YTDLP_PROXY` | | Residential proxy URL. Alternative to the above; skips Tailscale. |
| `YT_COOKIES` / `_B64` / `_FILE` | | Optional YouTube login cookies. Also lifts age restrictions. |

See **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** for the full reference,
including how to obtain Spotify credentials and export YouTube cookies.

## Deployment

TrackFlow is built to run on [Railway](https://railway.app/) with a persistent
volume and zero extra infrastructure. A one-page walkthrough — including the
critical volume setup that keeps user data across redeploys — is in
**[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

```bash
# Container build works anywhere Docker runs:
docker build -t trackflow .
docker run --env-file .env -p 8080:8080 -v "$(pwd)/data:/data" trackflow
```

## Bot commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/liked` | Download your Spotify Liked Songs |
| `/favorites` | Your saved favorites |
| `/settings` | Quality (128 / 320 kbps) and language |
| `/help` | Usage help |
| `/admin` | Admin control panel (authorized users only) |

## Architecture

```
bot/
├── main.py            # Entry point: polling loop + OAuth web server + lifecycle
├── config.py          # Environment-based settings (pydantic)
├── i18n.py            # Localized strings (UZ / EN / RU)
├── keyboards.py       # Inline keyboards
├── security.py        # Token encryption helpers
├── handlers/          # Telegram update handlers (links, search, library, video, …)
├── services/          # Core logic
│   ├── spotify.py     #   Async Spotify Web API client (metadata, OAuth, Liked)
│   ├── search_engine.py #  Query → best-match resolution
│   ├── matcher.py     #   Pick the closest YouTube source for a track
│   ├── downloader.py  #   yt-dlp → MP3 → ID3 tags + cover art
│   ├── queue.py       #   Caching, parallel downloads, progress, cancellation
│   ├── recognizer.py  #   Shazam-based music recognition
│   ├── recommender.py #   "Similar songs" engine
│   ├── video_dl.py    #   Social-media video downloads
│   └── audio_*.py     #   Effects and analysis
├── db/                # SQLite layer (users, file_id cache, history, tokens)
├── admin/             # Admin control panel (roles, bans, broadcast, dashboard)
└── web/oauth.py       # Spotify OAuth callback + /health endpoint
```

For a deeper tour of the request lifecycle and data flow, see
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Contributing

Contributions are welcome. Please read **[CONTRIBUTING.md](CONTRIBUTING.md)** for
the development setup, coding style, and pull-request workflow.

## License

Released under the [MIT License](LICENSE).
