from bot.db.database import db


# --- Foydalanuvchilar ---

async def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    await db().execute(
        """INSERT INTO users(id, username, first_name) VALUES(?,?,?)
           ON CONFLICT(id) DO UPDATE SET username=excluded.username,
                                         first_name=excluded.first_name""",
        (user_id, username, first_name),
    )
    await db().commit()


async def get_quality(user_id: int) -> str:
    cur = await db().execute("SELECT quality FROM users WHERE id=?", (user_id,))
    row = await cur.fetchone()
    return row["quality"] if row else "320"


async def set_quality(user_id: int, quality: str) -> None:
    await db().execute("UPDATE users SET quality=? WHERE id=?", (quality, user_id))
    await db().commit()


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
    await db().commit()


async def get_history(user_id: int, limit: int = 10):
    cur = await db().execute(
        """SELECT spotify_id, title, artist, MAX(id) AS last_id
           FROM history WHERE user_id=?
           GROUP BY spotify_id ORDER BY last_id DESC LIMIT ?""",
        (user_id, limit),
    )
    return await cur.fetchall()


# --- Spotify tokenlar (shifrlangan holda saqlanadi) ---

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


# --- Statistika ---

async def incr(key: str, by: int = 1) -> None:
    await db().execute(
        """INSERT INTO counters(key, value) VALUES(?,?)
           ON CONFLICT(key) DO UPDATE SET value=value+excluded.value""",
        (key, by),
    )
    await db().commit()


async def get_stats() -> dict:
    async def one(sql: str) -> int:
        cur = await db().execute(sql)
        row = await cur.fetchone()
        return row[0] or 0

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
