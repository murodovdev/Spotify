"""SQLite ma'lumotlar qatlami: ulanish, sxema va xavfsiz migratsiya.

Persistence: Railway'da DB **volume**da (`/data/bot.db`) yashashi shart —
konteyner fayl tizimi har redeploy'da yo'qoladi. `init_db` volume'da emasligini
sezsa baland ovozda ogohlantiradi.

Migratsiya: `PRAGMA user_version` orqali. Har deployda mavjud ma'lumotni
o'chirmasdan bosqichma-bosqich yangilaydi. Migratsiyalar idempotent (ustun/jadval
bor-yo'qligini tekshiradi), shu sabab yangi va eski bazalarda bir xil ishlaydi.
"""

import logging
import os

import aiosqlite

log = logging.getLogger(__name__)

# Sxema versiyasi. Yangi migratsiya qo'shsangiz oshiring va _migrate() ga bosqich
# qo'shing.
SCHEMA_VERSION = 4

# Yangi o'rnatishlar uchun yakuniy sxema (idempotent). Eski bazalar _migrate()
# orqali shu holatga keltiriladi.
BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    quality     TEXT NOT NULL DEFAULT '320',
    lang        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    last_active REAL NOT NULL DEFAULT 0
);
-- idx_users_last_active _migrate() v3'да yaratiladi (eski bazada last_active
-- ustuni ALTER'dan keyin paydo bo'ladi — BASE_SCHEMA _migrate'дан oldin ishga
-- tushadi, shu sabab bu yerда indeks yaratib bo'lmaydi).

-- Yuklab olingan audio uchun Telegram file_id keshi. last_used LRU eviction
-- uchun (background maintenance eng kam ishlatilganini o'chiradi).
CREATE TABLE IF NOT EXISTS track_cache(
    spotify_id  TEXT NOT NULL,
    bitrate     TEXT NOT NULL,
    file_id     TEXT NOT NULL,
    title       TEXT,
    artist      TEXT,
    last_used   REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (spotify_id, bitrate)
);
-- idx_track_cache_last_used _migrate() da yaratiladi (eski bazada last_used
-- ustuni ALTER'dan keyin paydo bo'ladi, shu sabab bu yerda emas).

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

-- Tavsiya dvigateli: trek xususiyatlari keshi (Deezer/iTunes/MBID/audio-vektor JSON)
CREATE TABLE IF NOT EXISTS rec_features(
    key         TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rec_features_updated ON rec_features(updated_at);

-- Tavsiya dvigateli: rotatsiya xotirasi — (user, seed) uchun ko'rsatilgan treklar
CREATE TABLE IF NOT EXISTS rec_shown(
    user_id    INTEGER NOT NULL,
    seed_key   TEXT NOT NULL,
    track_key  TEXT NOT NULL,
    shown_at   REAL NOT NULL,
    PRIMARY KEY (user_id, seed_key, track_key)
);
CREATE INDEX IF NOT EXISTS idx_rec_shown_time ON rec_shown(shown_at);

-- ────────────────────────────────────────────────────────────────────────
-- Admin boshqaruv tizimi (v3)
-- ────────────────────────────────────────────────────────────────────────

-- Foydalanuvchi faolligi: active-users hisoblari uchun (last_active indeksli).
-- users.last_active ustuni migratsiyada ALTER bilan qo'shiladi (eski baza uchun),
-- fresh bazada esa quyida CREATE TABLE users ichida bo'lishi kerak — lekin users
-- yuqorida e'lon qilingan, shu sabab bu yerda faqat indeks (ustunни _migrate ham,
-- fresh uchun esa quyidagi ALTER-guard beradi).

-- Admin rollari: super | admin | moderator. config.admin_id doim super hisoblanadi.
CREATE TABLE IF NOT EXISTS admins(
    user_id   INTEGER PRIMARY KEY,
    role      TEXT NOT NULL DEFAULT 'admin',
    added_by  INTEGER,
    added_at  REAL NOT NULL DEFAULT 0
);

-- Bloklash / vaqtincha to'xtatish. until=0 → doimiy.
CREATE TABLE IF NOT EXISTS bans(
    user_id  INTEGER PRIMARY KEY,
    kind     TEXT NOT NULL DEFAULT 'ban',   -- ban | suspend
    reason   TEXT,
    until    REAL NOT NULL DEFAULT 0,
    by       INTEGER,
    at       REAL NOT NULL DEFAULT 0
);

-- Botni Telegram orqali sozlash (feature flag, maintenance, limitlar, welcome…).
CREATE TABLE IF NOT EXISTS bot_settings(
    key    TEXT PRIMARY KEY,
    value  TEXT
);

-- Majburiy obuna: botdan foydalanishdan oldin qo'shilishi shart bo'lgan
-- kanal/guruhlar. Faqat admin panel orqali boshqariladi — hech qanday chat id
-- kodда qattiq yozilmaydi.
CREATE TABLE IF NOT EXISTS force_subs(
    chat_id      INTEGER PRIMARY KEY,
    username     TEXT,               -- '@' siz, mavjud bo'lsa
    title        TEXT NOT NULL,
    kind         TEXT NOT NULL,      -- 'channel' | 'group'
    invite_link  TEXT,               -- maxfiy chatlar uchun yagona kirish yo'li
    enabled      INTEGER NOT NULL DEFAULT 1,
    sort_order   INTEGER NOT NULL DEFAULT 0
);

-- Har bir sezgir admin amali uchun audit izi.
CREATE TABLE IF NOT EXISTS audit_log(
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id  INTEGER NOT NULL,
    action    TEXT NOT NULL,
    target    TEXT,
    detail    TEXT,
    at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at DESC);

-- Kunlik hisoblagichlar (bugun/hafta/oy analitikasi). day = 'YYYY-MM-DD' (UTC).
CREATE TABLE IF NOT EXISTS daily_counters(
    day    TEXT NOT NULL,
    key    TEXT NOT NULL,
    value  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, key)
);
CREATE INDEX IF NOT EXISTS idx_daily_counters_key ON daily_counters(key, day);

-- Qo'shiq darajasidagi statistika: eng ko'p yuklab olingan / qidirilgan / tanilgan.
CREATE TABLE IF NOT EXISTS song_stats(
    key           TEXT PRIMARY KEY,   -- normallashgan "artist — title"
    title         TEXT,
    artist        TEXT,
    downloads     INTEGER NOT NULL DEFAULT 0,
    searches      INTEGER NOT NULL DEFAULT 0,
    recognitions  INTEGER NOT NULL DEFAULT 0,
    updated_at    REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_song_stats_dl ON song_stats(downloads DESC);
CREATE INDEX IF NOT EXISTS idx_song_stats_sr ON song_stats(searches DESC);
CREATE INDEX IF NOT EXISTS idx_song_stats_rc ON song_stats(recognitions DESC);

-- Muvaffaqiyatsiz qidiruv / tanish (music management uchun).
CREATE TABLE IF NOT EXISTS failed_events(
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    kind   TEXT NOT NULL,     -- search | recognize
    query  TEXT,
    at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_failed_events_at ON failed_events(kind, at DESC);

-- Broadcast tarixi va yetkazib berish statistikasi.
CREATE TABLE IF NOT EXISTS broadcasts(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id      INTEGER,
    kind          TEXT,
    status        TEXT NOT NULL DEFAULT 'pending', -- pending|running|done|cancelled|failed
    total         INTEGER NOT NULL DEFAULT 0,
    sent          INTEGER NOT NULL DEFAULT 0,
    failed        INTEGER NOT NULL DEFAULT 0,
    scheduled_at  REAL NOT NULL DEFAULT 0,
    created_at    REAL NOT NULL,
    finished_at   REAL NOT NULL DEFAULT 0
);
"""

_db: aiosqlite.Connection | None = None
_db_path: str = ""


async def _column_exists(table: str, column: str) -> bool:
    cur = await _db.execute(f"PRAGMA table_info({table})")
    return any(row["name"] == column for row in await cur.fetchall())


async def _migrate() -> None:
    """user_version dan SCHEMA_VERSION gacha bosqichma-bosqich, idempotent."""
    cur = await _db.execute("PRAGMA user_version")
    version = (await cur.fetchone())[0]
    if version >= SCHEMA_VERSION:
        return

    if version < 1:
        # v1: users.lang ustuni (avval ad-hoc ALTER edi)
        if not await _column_exists("users", "lang"):
            await _db.execute("ALTER TABLE users ADD COLUMN lang TEXT")

    if version < 2:
        # v2: track_cache.last_used + LRU indeks; write-only history jadvalini o'chirish
        if not await _column_exists("track_cache", "last_used"):
            await _db.execute(
                "ALTER TABLE track_cache ADD COLUMN last_used REAL NOT NULL DEFAULT 0"
            )
        await _db.execute(
            "CREATE INDEX IF NOT EXISTS idx_track_cache_last_used ON track_cache(last_used)"
        )
        await _db.execute("DROP TABLE IF EXISTS history")

    if version < 3:
        # v3: admin boshqaruv tizimi. Yangi jadvallar BASE_SCHEMA (CREATE IF NOT
        # EXISTS) orqali allaqachon yaratildi; bu yerda faqat mavjud users
        # jadvaliga last_active ustunini qo'shamiz.
        if not await _column_exists("users", "last_active"):
            await _db.execute(
                "ALTER TABLE users ADD COLUMN last_active REAL NOT NULL DEFAULT 0"
            )
        await _db.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active)"
        )

    if version < 4:
        # v4: majburiy obuna (force_subs). Jadval BASE_SCHEMA (CREATE IF NOT
        # EXISTS) orqali yaratildi; bu yerda faqat tartiblash indeksi.
        await _db.execute(
            "CREATE INDEX IF NOT EXISTS idx_force_subs_order "
            "ON force_subs(enabled, sort_order)"
        )

    await _db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    await _db.commit()
    log.info("DB migratsiya: v%s → v%s", version, SCHEMA_VERSION)


def _check_persistence(path: str) -> None:
    """Railway'da DB volume'da emasligini sezsa ogohlantiradi (ma'lumot yo'qolmasin)."""
    if not os.getenv("RAILWAY_ENVIRONMENT"):
        return
    abs_path = os.path.abspath(path)
    if not abs_path.startswith("/data"):
        log.warning(
            "⚠️  DB volume'da EMAS: %s — Railway redeploy'da BARCHA ma'lumot yo'qoladi! "
            "Railway'da /data ga Volume mount qiling va DB_PATH=/data/bot.db qo'ying.",
            abs_path,
        )


async def init_db(path: str) -> None:
    global _db, _db_path
    _db_path = path
    _check_persistence(path)
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
    # Bo'sh sahifalarni disk'ga qaytarish uchun (maintenance incremental_vacuum
    # chaqiradi). Fresh bazada darhol, mavjud bazada VACUUM'dan keyin kuchga kiradi.
    await _db.execute("PRAGMA auto_vacuum=INCREMENTAL")
    await _db.executescript(BASE_SCHEMA)
    await _migrate()
    await _db.commit()


def db() -> aiosqlite.Connection:
    assert _db is not None, "init_db() chaqirilmagan"
    return _db


def db_path() -> str:
    return _db_path


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
