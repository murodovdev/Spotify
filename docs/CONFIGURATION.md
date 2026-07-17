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
| `YT_COOKIES` | | — | Raw `cookies.txt` contents. |
| `YT_COOKIES_B64` | | — | Base64-encoded `cookies.txt` (convenient for Railway). |
| `YT_COOKIES_FILE` | | — | Path to a cookies file, e.g. `/data/cookies.txt`. |
| `TS_AUTHKEY` | | — | Tailscale auth key — routes YouTube out via a home exit node. |
| `TS_EXIT_NODE` | | — | Exit node hostname or `100.x` IP. Required with `TS_AUTHKEY`. |
| `TS_HOSTNAME` | | `trackflow-bot` | Device name in the tailnet. |
| `TS_SOCKS_PORT` | | `1055` | Local SOCKS5 port `tailscaled` listens on. |
| `YTDLP_PROXY` | | — | Residential proxy URL. Set it to skip Tailscale. |

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

## YouTube bot checks ("Sign in to confirm you're not a bot")

YouTube blocks data-center IPs (Railway) with this error. The block is on the
**IP's reputation, not on the absence of cookies** — yt-dlp's own docs note that
a cookieless "guest session" is good for ~300 videos/hour, but only from a clean
IP. Changing `player_client` does not help: as of yt-dlp
[#15865](https://github.com/yt-dlp/yt-dlp/issues/15865) even `android_vr` returns
`LOGIN_REQUIRED` from a flagged IP. So there are two fixes, and they are
alternatives — you need **one**.

### Option A — move the egress IP (works without cookies)

Free: run [Tailscale](https://tailscale.com) on a home machine that stays
powered on, and route only YouTube traffic through it.

1. At home: `tailscale up --advertise-exit-node`, then approve the exit node in
   the Tailscale admin console.
2. Set `TS_AUTHKEY` (a reusable auth key) and `TS_EXIT_NODE` (the exit node's
   hostname or `100.x` address).

At startup the bot brings up `tailscaled` in userspace mode (no TUN device
needed), verifies that traffic really leaves via the exit node, and logs both
IPs. If the check fails it leaves the proxy unset and carries on directly —
a broken proxy would break every download. Only YouTube bytes are relayed
(~4 MB/track); ffmpeg, the database and Telegram all stay on Railway.

Paid alternative: set `YTDLP_PROXY` to a residential proxy (~$1/GB ≈ 250
tracks/GB). Tailscale is skipped when `YTDLP_PROXY` is already set.

### Option B — login cookies

Also lifts age restrictions. Prefer a burner account: the account can get banned.

1. Install a browser extension that exports cookies in **Netscape `cookies.txt`
   format** while logged in to YouTube.
2. Provide the cookies through **one** of:
   - `YT_COOKIES_B64` — base64-encode the file. **Strongly preferred:** the
     Netscape format is tab-separated, and Railway's env fields turn tabs into
     spaces, which makes yt-dlp skip every line and silently read 0 cookies.
   - `YT_COOKIES` — paste the file contents directly (tabs are repaired on load).
   - `YT_COOKIES_FILE` — point to a file on a mounted volume, e.g.
     `/data/cookies.txt`. Note that yt-dlp **rewrites** this file with refreshed
     session cookies.

The bot logs how many cookies it read and whether a login cookie is present, so
a broken or logged-out export is visible immediately. If the export is unusable
it is discarded rather than passed to yt-dlp — supplying a cookie file makes
yt-dlp skip the `android_vr` client entirely, which would be strictly worse.

Cookie files are secrets — they are matched by `.gitignore` and must never be
committed.

## Token encryption

User OAuth tokens are encrypted at rest with Fernet. If `ENCRYPTION_KEY` is
unset, a key is derived deterministically from `BOT_TOKEN`. Set an explicit
`ENCRYPTION_KEY` if you want token encryption to survive a bot-token rotation.
