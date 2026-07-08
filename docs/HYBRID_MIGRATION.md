# Hybrid media architecture — migration plan

Goal: move heavy media work (`yt-dlp`, `ffmpeg`) off Railway onto a dedicated VPS
media server, keep Railway lightweight, and support large files via Telegram's
Local Bot API Server.

The migration is incremental. Each phase deploys and reverts independently.

## Ground truth

Three facts about the current system constrain every design below.

| Assumption | Reality |
|---|---|
| Railway runs PostgreSQL, Redis, Celery | None exist. SQLite (`aiosqlite`), in-memory `OrderedDict` stores, `asyncio.Semaphore` for concurrency |
| Media processing blocks horizontal scaling | It does not. `numReplicas = 1` is pinned by the SQLite volume and by long-polling (`TelegramConflictError`) |
| A `file_id` works anywhere | It does not. A `file_id` is scoped to the API server that issued it |

## The `file_id` constraint

`track_cache` is keyed on `file_id`, and every post-download button re-sends by
`file_id`. A file uploaded through a Local Bot API Server yields a `file_id` the
**cloud API cannot resolve**, and vice versa. Migrating a token to a local server
also requires calling `logOut` first, after which existing cloud `file_id`s stop
resolving.

So before Phase 3, one of these must be chosen:

1. **The bot also talks to the local API** — `Bot(session=AiohttpSession(api=TelegramAPIServer.from_base(...)))`.
   Every `sendMessage` then crosses Railway → VPS: needs TLS, auth, and costs latency.
2. **Key the cache by backend** — add an `api_backend` column to `track_cache` so
   cloud and local ids never mix. Simpler, but a file uploaded via the local
   server can never be re-sent through the cloud API.

This does not block Phases 1–2, but it must be decided before Phase 3.

## Phases

### Phase 0 — the media seam ✅ done

`bot/services/media/`: the `MediaBackend` interface (`base.py`), `LocalBackend`
(`local.py`) preserving today's exact behavior, and a `RemoteBackend` placeholder
(`remote.py`). All four heavy call sites now go through `media.backend()`.

- No behavior change. `MEDIA_BACKEND=local` is the default.
- New exception `MediaUnavailable`: the backend is temporarily down, so a retry
  makes sense. Distinct from `TrackNotFound`, where the track itself is the problem.
- `MEDIA_BACKEND=remote` raises `NotImplementedError` at **startup**, not at the
  first download — a loud failure beats a backend that silently does nothing.

### Phase 1 — the VPS media service

An aiohttp app with `yt-dlp` + `ffmpeg`. `POST /jobs`, authenticated with an
HMAC-SHA256 signature over `timestamp.nonce.body`; the server rejects stale
timestamps (replay protection). Streaming download → process → upload, with the
temp directory cleaned on every exit path. `RemoteBackend` speaks this API.
Railway CPU usage drops here.

### Phase 2 — fault tolerance

A `job_outbox` table (schema v4). If the VPS is down, jobs are queued rather than
lost, and retried with backoff. `MediaUnavailable` surfaces to the user as a
localized "queued, hang on" message. The bot stays responsive.

### Phase 3 — Local Bot API Server

Large-file support (up to 2 GB). The `file_id` decision above is implemented here,
along with the corresponding cache migration.

**Groundwork done.** Size limits are now a property of the active API mode rather
than five hardcoded constants (`bot/services/tg_limits.py`), and `main.py` builds
an `AiohttpSession` pointed at a local server when `TELEGRAM_API_MODE=local`.
Setting that env var is *not* yet sufficient — see the two blockers below.

#### There is no per-file fallback

A token cannot use the cloud API and a local server at the same time: Telegram's
workflow is `logOut` from the cloud, then launch locally. "Use the local server
when a file exceeds 50 MB" is therefore not implementable as a runtime switch.
The mode is chosen at deploy time, for the whole bot.

The graceful path when a file will not fit is to **offer a smaller format**, which
the YouTube format picker now does (`video_dl.smaller_formats`): a 60 MB FLAC on
the cloud API re-renders the keyboard with MP3 / M4A / OPUS rather than failing.

#### Remaining blockers before `TELEGRAM_API_MODE=local` is usable

1. **`file_id` invalidation.** Existing cloud `file_id`s in `track_cache` stop
   resolving after `logOut`. Decide between the two options above and migrate.
2. **Uploads must not cross the network.** A local server accepts an *absolute
   path* in `sendAudio` instead of a multipart upload — a 2 GB file is then never
   uploaded, just read off disk. This only works when the process calling
   `sendAudio` shares a filesystem with the API server. A Railway bot talking to a
   VPS local server would still POST 2 GB over the wire. So in the final design the
   **media server** issues the send, not Railway (step 7 of the job flow), and
   `wrap_local_file` must be configured accordingly.

Until then, `TELEGRAM_API_MODE=local` is only correct for a single-box deployment
where the bot, the media work, and the API server all live together.

### Phase 4 — Postgres + Redis + Celery (optional)

Only if multi-replica is actually wanted; this is what unpins `numReplicas`. It is
larger than Phases 0–3 combined, and doing it alongside the service split would
make both changes unreviewable.

## Module boundaries

```
bot/handlers/       → Telegram UI (aiogram)
bot/services/       → business logic (search, recommendation, recognition)
bot/services/media/ → heavy-media boundary   ← the Railway/VPS split lives here
bot/db/             → persistence
```

Heavy media work is reached only through `media.backend()`.

## Configuration

| Env | Default | Meaning |
|---|---|---|
| `MEDIA_BACKEND` | `local` | `local` (in-process) or `remote` (VPS, Phase 1) |
| `MEDIA_SERVER_URL` | — | Base URL of the media service; required when remote |
| `MEDIA_SERVER_SECRET` | — | HMAC signing secret shared with the media service |
| `TELEGRAM_API_MODE` | `cloud` | `cloud` (50 MB uploads, 20 MB downloads) or `local` (2 GB) |
| `TELEGRAM_API_BASE` | — | Local Bot API Server base URL, e.g. `http://127.0.0.1:8081`; required when local |

Size limits are never hardcoded at a call site. Ask `bot/services/tg_limits.py`:
`max_upload_bytes()` and `max_download_bytes()` read the active mode at call time.
