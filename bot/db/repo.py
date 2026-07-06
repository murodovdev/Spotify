import asyncio
import time

from bot.db.database import db

_user_cache: dict[int, dict] = {}
_CACHE_MAX = 100_000

_dirty = False
_last_flush: float = 0
_FLUSH_INTERVAL = 2.0


def _evict(user_id: int) -> None:
    _user_cache.pop(user_id, None)


async def _mark_dirty() -> None:
    global _dirty, _last_flush
    _dirty = True
    now = time.monotonic()
    if now - _last_flush >= _FLUSH_INTERVAL:
        await flush()


async def flush() -> None:
    global _dirty, _last_flush
    if _dirty:
        await db().commit()
        _dirty = False
    _last_flush = time.monotonic()


async def _ensure_user(user_id: int) -> dict:
    cached = _user_cache.get(user_id)
    if cached is not None:
        return cached
    cur = await db().execute("SELECT quality, lang FROM users WHERE id=?", (user_id,))
    row = await cur.fetchone()
    if row:
        entry = {"quality": row["quality"], "lang": row["lang"]}
    else:
        entry = {"quality": "320", "lang": None}
    if len(_user_cache) < _CACHE_MAX:
        _user_cache[user_id] = entry
    return entry


# --- Foydalanuvchilar ---

async def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    await db().execute(
        """INSERT INTO users(id, username, first_name) VALUES(?,?,?)
           ON CONFLICT(id) DO UPDATE SET username=excluded.username,
                                         first_name=excluded.first_name""",
        (user_id, username, first_name),
    )
    await _mark_dirty()


async def get_quality(user_id: int) -> str:
    return (await _ensure_user(user_id))["quality"]


async def set_quality(user_id: int, quality: str) -> None:
    await db().execute("UPDATE users SET quality=? WHERE id=?", (quality, user_id))
    await db().commit()
    cached = _user_cache.get(user_id)
    if cached:
        cached["quality"] = quality


async def get_lang(user_id: int) -> str | None:
    return (await _ensure_user(user_id))["lang"]


async def set_lang(user_id: int, lang: str) -> None:
    await db().execute("UPDATE users SET lang=? WHERE id=?", (lang, user_id))
    await db().commit()
    cached = _user_cache.get(user_id)
    if cached:
        cached["lang"] = lang


# --- file_id kesh ---

async def cache_get(spotify_id: str, bitrate: str) -> str | None:
    cur = await db().execute(
        "SELECT file_id FROM track_cache WHERE spotify_id=? AND bitrate=?",
        (spotify_id, bitrate),
    )
    row = await cur.fetchone()
    return row["file_id"] if row else None


async def cache_any_row(spotify_id: str):
    cur = await db().execute(
        "SELECT title, artist FROM track_cache WHERE spotify_id=? LIMIT 1",
        (spotify_id,),
    )
    return await cur.fetchone()


async def cache_put(spotify_id: str, bitrate: str, file_id: str, title: str, artist: str) -> None:
    await db().execute(
        """INSERT INTO track_cache(spotify_id, bitrate, file_id, title, artist)
           VALUES(?,?,?,?,?)
           ON CONFLICT(spotify_id, bitrate) DO UPDATE SET file_id=excluded.file_id""",
        (spotify_id, bitrate, file_id, title, artist),
    )
    await db().commit()


# --- Tarix ---

async def add_history(user_id: int, spotify_id: str, title: str, artist: str) -> None:
    await db().execute(
        "INSERT INTO history(user_id, spotify_id, title, artist) VALUES(?,?,?,?)",
        (user_id, spotify_id, title, artist),
    )
    await _mark_dirty()


# --- Sevimlilar ---

async def is_favorite(user_id: int, spotify_id: str) -> bool:
    cur = await db().execute(
        "SELECT 1 FROM favorites WHERE user_id=? AND spotify_id=?",
        (user_id, spotify_id),
    )
    return await cur.fetchone() is not None


async def toggle_favorite(user_id: int, spotify_id: str, title: str, artist: str) -> bool:
    """Sevimlilarga qo'shadi yoki olib tashlaydi. Qaytaradi: yakuniy holat (True = saqlangan)."""
    if await is_favorite(user_id, spotify_id):
        await db().execute(
            "DELETE FROM favorites WHERE user_id=? AND spotify_id=?",
            (user_id, spotify_id),
        )
        await db().commit()
        return False
    await db().execute(
        """INSERT INTO favorites(user_id, spotify_id, title, artist) VALUES(?,?,?,?)
           ON CONFLICT(user_id, spotify_id) DO NOTHING""",
        (user_id, spotify_id, title, artist),
    )
    await db().commit()
    return True


async def list_favorites(user_id: int, limit: int = 50) -> list:
    cur = await db().execute(
        """SELECT spotify_id, title, artist FROM favorites
           WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    )
    return await cur.fetchall()


# --- Spotify tokenlar ---

async def save_tokens(user_id: int, refresh_enc: str, access_enc: str, expires_at: float) -> None:
    await db().execute(
        """INSERT INTO spotify_tokens(user_id, refresh_token, access_token, expires_at)
           VALUES(?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET refresh_token=excluded.refresh_token,
                                              access_token=excluded.access_token,
                                              expires_at=excluded.expires_at""",
        (user_id, refresh_enc, access_enc, expires_at),
    )
    await db().commit()


async def get_tokens(user_id: int):
    cur = await db().execute(
        "SELECT refresh_token, access_token, expires_at FROM spotify_tokens WHERE user_id=?",
        (user_id,),
    )
    return await cur.fetchone()


async def delete_tokens(user_id: int) -> None:
    await db().execute("DELETE FROM spotify_tokens WHERE user_id=?", (user_id,))
    await db().commit()


async def is_connected(user_id: int) -> bool:
    return await get_tokens(user_id) is not None


# --- Tavsiya dvigateli keshlari ---

_REC_FEAT_MAX = 25_000


async def rec_feat_get(key: str) -> str | None:
    cur = await db().execute("SELECT payload FROM rec_features WHERE key=?", (key,))
    row = await cur.fetchone()
    return row["payload"] if row else None


async def rec_feat_put(key: str, payload: str) -> None:
    await db().execute(
        """INSERT INTO rec_features(key, payload, updated_at) VALUES(?,?,?)
           ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,
                                          updated_at=excluded.updated_at""",
        (key, payload, time.time()),
    )
    # Vaqti-vaqti bilan eng eski yozuvlarni tozalaymiz (jadval cheksiz o'smasin)
    if int(time.time()) % 97 == 0:
        await db().execute(
            """DELETE FROM rec_features WHERE key NOT IN
               (SELECT key FROM rec_features ORDER BY updated_at DESC LIMIT ?)""",
            (_REC_FEAT_MAX,),
        )
    await _mark_dirty()


async def rec_shown_get(user_id: int, seed_key: str, since: float) -> set[str]:
    cur = await db().execute(
        "SELECT track_key FROM rec_shown WHERE user_id=? AND seed_key=? AND shown_at>=?",
        (user_id, seed_key, since),
    )
    return {row["track_key"] for row in await cur.fetchall()}


async def rec_shown_add(user_id: int, seed_key: str, track_keys: list[str]) -> None:
    now = time.time()
    await db().executemany(
        """INSERT INTO rec_shown(user_id, seed_key, track_key, shown_at) VALUES(?,?,?,?)
           ON CONFLICT(user_id, seed_key, track_key) DO UPDATE SET shown_at=excluded.shown_at""",
        [(user_id, seed_key, k, now) for k in track_keys],
    )
    await db().execute("DELETE FROM rec_shown WHERE shown_at < ?", (now - 45 * 86400,))
    await _mark_dirty()


# --- Statistika ---

async def incr(key: str, by: int = 1) -> None:
    await db().execute(
        """INSERT INTO counters(key, value) VALUES(?,?)
           ON CONFLICT(key) DO UPDATE SET value=value+excluded.value""",
        (key, by),
    )
    await _mark_dirty()


async def get_stats() -> dict:
    async def one(sql: str) -> int:
        cur = await db().execute(sql)
        row = await cur.fetchone()
        return row[0] or 0

    await flush()
    users = await one("SELECT COUNT(*) FROM users")
    cached = await one("SELECT COUNT(*) FROM track_cache")
    downloads = await one(
        "SELECT COALESCE(SUM(value),0) FROM counters WHERE key='downloads'"
    )
    cache_hits = await one(
        "SELECT COALESCE(SUM(value),0) FROM counters WHERE key='cache_hits'"
    )
    total = downloads + cache_hits
    return {
        "users": users,
        "cached": cached,
        "downloads": downloads,
        "cache_hits": cache_hits,
        "hit_rate": round(cache_hits * 100 / total) if total else 0,
    }
