"""Admin ma'lumot qatlami — ban, sozlama, statistika, audit, broadcast so'rovlari.

Barcha admin yozuvlari darhol commit qilinadi (amallar kam uchraydi, to'g'rilik
batchlashдан muhim). O'qishlar sahifalangan va indekslarга tayanadi — bot yuz
minglab foydalanuvchiга o'ssa ham xotiraга katta to'plam yuklanmaydi.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from bot.admin import roles
from bot.config import settings as cfg
from bot.db import repo as core_repo
from bot.db.database import db


# Bloklangan foydalanuvchilar in-memory keshi. Har xabar/bosishда middleware
# buni tekshiradi — 99.99% (bloklanmagan) foydalanuvchi uchun DB o'qishsiz.
# Bans jadvali kichik, shu sabab startupда to'liq yuklanadi.
_ban_cache: dict[int, tuple[str, str | None, float]] = {}

# Admin ID → rol keshi. AdminFilter HAR xabar/bosishда rolни tekshiradi, shu
# sabab bu DB emas, xotiradан o'qilishi shart (hot path).
_admin_cache: dict[int, str] = {}


def _now() -> float:
    return time.time()


async def load_bans() -> None:
    """init_db'дан keyin bir marta — ban keshini to'ldiradi."""
    _ban_cache.clear()
    cur = await db().execute("SELECT user_id, kind, reason, until FROM bans")
    for r in await cur.fetchall():
        _ban_cache[r["user_id"]] = (r["kind"], r["reason"], r["until"])


async def load_admins() -> None:
    """init_db'дан keyin bir marta — admin rol keshini to'ldiradi."""
    _admin_cache.clear()
    cur = await db().execute("SELECT user_id, role FROM admins")
    for r in await cur.fetchall():
        _admin_cache[r["user_id"]] = r["role"]


def cached_block(user_id: int) -> tuple[bool, str | None]:
    """(bloklanganmi, sabab). Muddati o'tган suspend uchun sabab '__expired__'."""
    ent = _ban_cache.get(user_id)
    if ent is None:
        return False, None
    _kind, reason, until = ent
    if until and until <= time.time():
        return False, "__expired__"
    return True, reason


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ─────────────────────────── Adminlar & rollar ──────────────────────────────

async def get_role(user_id: int) -> str | None:
    """Foydalanuvchining admin roli yoki None. config.admin_id doim super.

    Faqat in-memory kesh (hot path) — DB o'qishsiz. Kesh startupда va
    add/remove_admin'да yangilanadi.
    """
    if cfg.admin_id and user_id == cfg.admin_id:
        return roles.ROLE_SUPER
    return _admin_cache.get(user_id)


async def list_admins() -> list:
    cur = await db().execute(
        "SELECT user_id, role, added_by, added_at FROM admins ORDER BY added_at"
    )
    return await cur.fetchall()


async def add_admin(user_id: int, role: str, by: int) -> None:
    await db().execute(
        """INSERT INTO admins(user_id, role, added_by, added_at) VALUES(?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET role=excluded.role""",
        (user_id, role, by, _now()),
    )
    await db().commit()
    _admin_cache[user_id] = role


async def remove_admin(user_id: int) -> None:
    await db().execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    await db().commit()
    _admin_cache.pop(user_id, None)


# ─────────────────────────────── Bloklash ───────────────────────────────────

async def set_ban(user_id: int, kind: str, reason: str | None, until: float, by: int) -> None:
    await db().execute(
        """INSERT INTO bans(user_id, kind, reason, until, by, at) VALUES(?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET kind=excluded.kind, reason=excluded.reason,
                                              until=excluded.until, by=excluded.by, at=excluded.at""",
        (user_id, kind, reason, until, by, _now()),
    )
    await db().commit()
    _ban_cache[user_id] = (kind, reason, until)


async def unban(user_id: int) -> None:
    await db().execute("DELETE FROM bans WHERE user_id=?", (user_id,))
    await db().commit()
    _ban_cache.pop(user_id, None)


async def get_ban(user_id: int):
    cur = await db().execute(
        "SELECT user_id, kind, reason, until, by, at FROM bans WHERE user_id=?", (user_id,)
    )
    return await cur.fetchone()


async def is_blocked(user_id: int) -> tuple[bool, str | None]:
    """(bloklanganmi, sabab). Muddati o'tgan suspend avtomatik olib tashlanadi."""
    row = await get_ban(user_id)
    if not row:
        return False, None
    until = row["until"]
    if until and until <= _now():
        await unban(user_id)
        return False, None
    return True, row["reason"]


async def list_bans(offset: int = 0, limit: int = 8) -> list:
    cur = await db().execute(
        "SELECT user_id, kind, reason, until, at FROM bans ORDER BY at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return await cur.fetchall()


async def count_bans() -> int:
    cur = await db().execute("SELECT COUNT(*) FROM bans")
    return (await cur.fetchone())[0]


# ──────────────────────── Foydalanuvchi boshqaruvi ──────────────────────────

async def find_users(query: str, limit: int = 8) -> list:
    """ID yoki username (@ ixtiyoriy, qism) bo'yicha qidiradi."""
    query = query.strip().lstrip("@")
    if query.isdigit():
        cur = await db().execute(
            "SELECT id, username, first_name, lang, last_active FROM users WHERE id=?",
            (int(query),),
        )
    else:
        cur = await db().execute(
            """SELECT id, username, first_name, lang, last_active FROM users
               WHERE username LIKE ? OR first_name LIKE ? ORDER BY last_active DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        )
    return await cur.fetchall()


async def get_user(user_id: int):
    cur = await db().execute(
        """SELECT id, username, first_name, quality, lang, created_at, last_active
           FROM users WHERE id=?""",
        (user_id,),
    )
    return await cur.fetchone()


async def user_extras(user_id: int) -> dict:
    async def one(sql: str, *args) -> int:
        cur = await db().execute(sql, args)
        return (await cur.fetchone())[0] or 0

    fav = await one("SELECT COUNT(*) FROM favorites WHERE user_id=?", user_id)
    connected = await one("SELECT COUNT(*) FROM spotify_tokens WHERE user_id=?", user_id) > 0
    return {"favorites": fav, "connected": connected}


async def reset_user(user_id: int) -> None:
    """Sozlamalarni tiklaydi: sifat 320, til tozalanadi, sevimlilar o'chiriladi."""
    await db().execute(
        "UPDATE users SET quality='320', lang=NULL WHERE id=?", (user_id,)
    )
    await db().execute("DELETE FROM favorites WHERE user_id=?", (user_id,))
    await db().commit()


async def touch_last_active(user_id: int, ts: float) -> None:
    await db().execute("UPDATE users SET last_active=? WHERE id=?", (ts, user_id))


async def count_users() -> int:
    cur = await db().execute("SELECT COUNT(*) FROM users")
    return (await cur.fetchone())[0]


async def active_since(ts: float) -> int:
    cur = await db().execute("SELECT COUNT(*) FROM users WHERE last_active>=?", (ts,))
    return (await cur.fetchone())[0]


async def iter_active_user_ids(batch: int = 500):
    """Broadcast uchun: bloklanmagan foydalanuvchi ID'larини oqim tarzида beradi."""
    offset = 0
    while True:
        cur = await db().execute(
            """SELECT id FROM users WHERE id NOT IN (SELECT user_id FROM bans)
               ORDER BY id LIMIT ? OFFSET ?""",
            (batch, offset),
        )
        rows = await cur.fetchall()
        if not rows:
            break
        for r in rows:
            yield r["id"]
        offset += batch


async def delete_inactive(days: int) -> int:
    cutoff = _now() - days * 86400
    cur = await db().execute(
        "DELETE FROM users WHERE last_active>0 AND last_active<? AND id NOT IN "
        "(SELECT user_id FROM spotify_tokens)",
        (cutoff,),
    )
    await db().commit()
    return cur.rowcount


async def lang_counts() -> list:
    cur = await db().execute(
        "SELECT COALESCE(lang,'—') AS lang, COUNT(*) AS n FROM users GROUP BY lang ORDER BY n DESC"
    )
    return await cur.fetchall()


# ──────────────────────────────── Statistika ────────────────────────────────

async def incr_daily(key: str, by: int = 1) -> None:
    # Hot path (har yuklab olishда) — batched commit (2s flush) ishlatamiz.
    await db().execute(
        """INSERT INTO daily_counters(day, key, value) VALUES(?,?,?)
           ON CONFLICT(day, key) DO UPDATE SET value=value+excluded.value""",
        (_today(), key, by),
    )
    await core_repo.mark_dirty()


async def daily_sum(key: str, days: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    cur = await db().execute(
        "SELECT COALESCE(SUM(value),0) FROM daily_counters WHERE key=? AND day>=?",
        (key, cutoff),
    )
    return (await cur.fetchone())[0] or 0


async def bump_song(key: str, title: str, artist: str, field: str) -> None:
    if field not in ("downloads", "searches", "recognitions"):
        return
    await db().execute(
        f"""INSERT INTO song_stats(key, title, artist, {field}, updated_at)
            VALUES(?,?,?,1,?)
            ON CONFLICT(key) DO UPDATE SET {field}={field}+1,
                                           title=excluded.title, artist=excluded.artist,
                                           updated_at=excluded.updated_at""",
        (key, title, artist, _now()),
    )
    await core_repo.mark_dirty()


async def top_songs(field: str, limit: int = 10) -> list:
    if field not in ("downloads", "searches", "recognitions"):
        return []
    cur = await db().execute(
        f"SELECT title, artist, {field} AS n FROM song_stats WHERE {field}>0 "
        f"ORDER BY {field} DESC LIMIT ?",
        (limit,),
    )
    return await cur.fetchall()


async def add_failed(kind: str, query: str) -> None:
    await db().execute(
        "INSERT INTO failed_events(kind, query, at) VALUES(?,?,?)",
        (kind, query[:200], _now()),
    )
    await db().commit()


async def recent_failed(kind: str, limit: int = 10) -> list:
    cur = await db().execute(
        "SELECT query, at FROM failed_events WHERE kind=? ORDER BY at DESC LIMIT ?",
        (kind, limit),
    )
    return await cur.fetchall()


async def count_failed(kind: str, since: float) -> int:
    cur = await db().execute(
        "SELECT COUNT(*) FROM failed_events WHERE kind=? AND at>=?", (kind, since)
    )
    return (await cur.fetchone())[0]


# ─────────────────────────────── Audit izi ──────────────────────────────────

async def add_audit(admin_id: int, action: str, target: str | None = None,
                    detail: str | None = None) -> None:
    await db().execute(
        "INSERT INTO audit_log(admin_id, action, target, detail, at) VALUES(?,?,?,?,?)",
        (admin_id, action, target, detail, _now()),
    )
    await db().commit()


async def recent_audit(limit: int = 15, offset: int = 0) -> list:
    cur = await db().execute(
        "SELECT admin_id, action, target, detail, at FROM audit_log "
        "ORDER BY at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return await cur.fetchall()


# ────────────────────────────── Broadcast ───────────────────────────────────

async def create_broadcast(admin_id: int, kind: str, total: int, scheduled_at: float = 0) -> int:
    cur = await db().execute(
        """INSERT INTO broadcasts(admin_id, kind, status, total, scheduled_at, created_at)
           VALUES(?,?,?,?,?,?)""",
        (admin_id, kind, "running" if not scheduled_at else "pending",
         total, scheduled_at, _now()),
    )
    await db().commit()
    return cur.lastrowid


async def update_broadcast(bid: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    await db().execute(
        f"UPDATE broadcasts SET {cols} WHERE id=?", (*fields.values(), bid)
    )
    await db().commit()


async def recent_broadcasts(limit: int = 8) -> list:
    cur = await db().execute(
        "SELECT id, kind, status, total, sent, failed, created_at FROM broadcasts "
        "ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    return await cur.fetchall()


# ───────────────────────── DB salomatligi / hajmi ───────────────────────────

_TABLES = [
    "users", "track_cache", "favorites", "spotify_tokens", "counters",
    "rec_features", "rec_shown", "admins", "bans", "audit_log",
    "daily_counters", "song_stats", "failed_events", "broadcasts",
]


async def table_sizes() -> list[tuple[str, int]]:
    out = []
    for tbl in _TABLES:
        try:
            cur = await db().execute(f"SELECT COUNT(*) FROM {tbl}")
            out.append((tbl, (await cur.fetchone())[0]))
        except Exception:
            continue
    out.sort(key=lambda x: x[1], reverse=True)
    return out


async def db_size_bytes() -> int:
    cur = await db().execute("PRAGMA page_count")
    pages = (await cur.fetchone())[0]
    cur = await db().execute("PRAGMA page_size")
    size = (await cur.fetchone())[0]
    return pages * size


async def integrity_ok() -> bool:
    cur = await db().execute("PRAGMA quick_check")
    row = await cur.fetchone()
    return bool(row) and row[0] == "ok"
