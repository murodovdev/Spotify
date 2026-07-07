# Deployment Guide

TrackFlow ships as a single container and is designed to run on
[Railway](https://railway.app/) with a persistent volume. It works equally well
on any Docker host.

## Railway (recommended)

### 1. Push to GitHub

Push the repository to GitHub. Never commit `.env` or cookie files — they are
already covered by `.gitignore`.

### 2. Create the project

Railway → **New Project** → **Deploy from GitHub repo** → select this repository.
Railway detects the `Dockerfile` and builds automatically.

### 3. Set environment variables

Under **Variables**, add:

| Variable | Value |
|---|---|
| `BOT_TOKEN` | Token from @BotFather |
| `SPOTIFY_CLIENT_ID` | From the Spotify dashboard (optional) |
| `SPOTIFY_CLIENT_SECRET` | From the Spotify dashboard (optional) |
| `DB_PATH` | `/data/bot.db` |
| `ADMIN_ID` | Your Telegram user ID (optional) |

See [CONFIGURATION.md](CONFIGURATION.md) for the complete list.

### 4. Attach a persistent volume ⚠️

This step is mandatory. Without it, every redeploy wipes all user data
(the SQLite database, the `file_id` cache, and stored tokens).

- Right-click the service → **Attach Volume** → mount path: **`/data`**.
- The app writes to `/data/bot.db` automatically when `DB_PATH` is unset or set
  to `/data/bot.db`.

### 5. Generate a domain

**Settings → Networking → Generate Domain.** If prompted for a port, enter
`8080`. The generated domain hosts the Spotify OAuth callback and the
`/health` check that Railway monitors.

### 6. Configure the Spotify redirect URI

In the Spotify dashboard, set the app's **Redirect URI** to match your domain:

```
https://<your-domain>/callback
```

### Scaling note

Keep **`numReplicas = 1`** (set in `railway.toml`):

- A Railway volume attaches to only one instance.
- Telegram long-polling with two instances raises `TelegramConflictError`.

## Docker (any host)

```bash
docker build -t trackflow .
docker run -d \
  --name trackflow \
  --env-file .env \
  -p 8080:8080 \
  -v "$(pwd)/data:/data" \
  trackflow
```

Set `DB_PATH=/data/bot.db` in your `.env` so the database lands on the mounted
volume.

## Health check

The container exposes `GET /health` (and `/`) on `PORT` (default `8080`),
returning `200 OK`. Railway uses this via `healthcheckPath = "/health"` in
`railway.toml`.
