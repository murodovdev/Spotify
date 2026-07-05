import os

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    quality     TEXT NOT NULL DEFAULT '320',
    lang        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS track_cache(
    spotify_id  TEXT NOT NULL,
    bitrate     TEXT NOT NULL,
    file_id     TEXT NOT NULL,
    title       TEXT,
    artist      TEXT,
    PRIMARY KEY (spotify_id, bitrate)
);

CREATE TABLE IF NOT EXISTS history(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    spotify_id  TEXT NOT NULL,
    title       TEXT,
    artist      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id, id DESC);

CREATE TABLE IF NOT EXISTS spotify_tokens(
    user_id        INTEGER PRIMARY KEY,
    refresh_token  TEXT NOT NULL,
    access_token   TEXT,
    expires_at     REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS counters(
    key    TEXT PRIMARY KEY,
    value  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS favorites(
    user_id     INTEGER NOT NULL,
    spotify_id  TEXT NOT NULL,
    title       TEXT,
    artist      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, spotify_id)
);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, created_at DESC);
"""

_db: aiosqlite.Connection | None = None


async def init_db(path: str) -> None:
    global _db
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA synchronous=NORMAL")
    await _db.execute("PRAGMA cache_size=-8000")
    await _db.execute("PRAGMA busy_timeout=5000")
    await _db.execute("PRAGMA temp_store=MEMORY")
    await _db.execute("PRAGMA mmap_size=67108864")
    await _db.execute("PRAGMA wal_autocheckpoint=1000")
    await _db.executescript(SCHEMA)
    try:
        await _db.execute("ALTER TABLE users ADD COLUMN lang TEXT")
    except Exception:
        pass
    await _db.commit()


def db() -> aiosqlite.Connection:
    assert _db is not None, "init_db() chaqirilmagan"
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
