# Configuration Guide

All configuration is supplied through environment variables (loaded from a `.env`
file locally, or the platform's variable store in production). Only `BOT_TOKEN`
is required.

## Reference

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `BOT_TOKEN` | ✅ | — | Telegram bot token from [@BotFather](https://t.me/BotFather). |
| `SPOTIFY_CLIENT_ID` | | — | Spotify app client ID. Enables full API access and Liked Songs. |
| `SPOTIFY_CLIENT_SECRET` | | — | Spotify app client secret. |
| `SPOTIFY_REDIRECT_URI` | | auto | OAuth callback URL. Auto-derived when blank. |
| `ADMIN_ID` | | `0` | Telegram user ID granted owner/admin access. |
| `ENCRYPTION_KEY` | | derived | Fernet key for encrypting stored tokens. Derived from `BOT_TOKEN` if blank. |
| `DB_PATH` | | auto | SQLite path. `/data/bot.db` on Railway, `data/bot.db` locally. |
| `PORT` | | `8080` | Port for the OAuth web server / health check. |
| `MAX_DOWNLOADS` | | `4` | Maximum concurrent downloads. |
| `LASTFM_API_KEY` | | — | Optional. Strengthens the recommendation engine. |
| `YOUTUBE_COOKIES` | | — | Raw `cookies.txt` contents. |
| `YOUTUBE_COOKIES_B64` | | — | Base64-encoded `cookies.txt` (convenient for Railway). |
| `YOUTUBE_COOKIES_FILE` | | — | Path to a cookies file, e.g. `/data/cookies.txt`. |

> Railway also injects `RAILWAY_ENVIRONMENT` and `RAILWAY_PUBLIC_DOMAIN`
> automatically; TrackFlow reads them to auto-select the database path, bind
> address, and OAuth redirect URI. You do not set these yourself.

## Obtaining Spotify credentials

1. Sign in at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. **Create app**:
   - **Name / description** — anything.
   - **Redirect URI** — your deployment callback, e.g.
     `https://<your-domain>/callback` (add `http://127.0.0.1:8080/callback` for
     local testing).
   - **API used** — Web API.
3. Copy the **Client ID** and **Client Secret** into `SPOTIFY_CLIENT_ID` and
   `SPOTIFY_CLIENT_SECRET`.

### Embed mode (no credentials)

Without Spotify credentials, the bot still works in **embed mode**: it reads
metadata from public `open.spotify.com/embed` pages and resolves audio through
YouTube search. Limitations:

- Playlists are capped at roughly 50 tracks.
- **Liked Songs is unavailable** (it requires the official API and a Premium
  app owner account).

> Since 2025, Spotify requires the app owner's account to have **Premium** for
> Web API playback-related scopes. Embed mode exists specifically so the bot
> keeps working without Premium.

## YouTube cookies

YouTube frequently blocks data-center IPs ("Sign in to confirm you're not a
bot") and refuses age-restricted videos. Providing login cookies resolves both.

1. Install a browser extension that exports cookies in **Netscape `cookies.txt`
   format** while logged in to YouTube.
2. Provide the cookies through **one** of:
   - `YOUTUBE_COOKIES` — paste the file contents directly.
   - `YOUTUBE_COOKIES_B64` — base64-encode the file (best for Railway, avoids
     multiline-variable issues).
   - `YOUTUBE_COOKIES_FILE` — point to a file on a mounted volume, e.g.
     `/data/cookies.txt`.

Cookie files are secrets — they are matched by `.gitignore` and must never be
committed.

## Token encryption

User OAuth tokens are encrypted at rest with Fernet. If `ENCRYPTION_KEY` is
unset, a key is derived deterministically from `BOT_TOKEN`. Set an explicit
`ENCRYPTION_KEY` if you want token encryption to survive a bot-token rotation.
