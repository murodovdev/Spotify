"""Davriy DB maintenance: cache eviction, WAL checkpoint, vacuum, monitoring.

Bitta background task (main.py da) buni davriy chaqiradi. Maqsad: storage'ni
cheklab turish (5 GB Railway Hobby limiti), disk'ni tejash va o'sishни kuzatish.
Har yozuvда qimmat tozalash o'rniga hammasi shu yerда to'plangan.
"""

import asyncio
import logging
import os
import time

from bot.db.database import db, db_path

log = logging.getLogger(__name__)

# Cheklovlar — storage'ni jilovlash uchun
TRACK_CACHE_MAX = 500_000      # file_id keshi (eng kam ishlatilgani o'chadi)
REC_FEAT_MAX = 25_000          # tavsiya xususiyatlari keshi
REC_SHOWN_DAYS = 45            # rotatsiya xotirasi umri

_INTERVAL = 6 * 3600           # har 6 soatda
_FIRST_DELAY = 90              # ishga tushgach ~90s dan keyin birinchi marta


async def _count(table: str) -> int:
    cur = await db().execute(f"SELECT COUNT(*) FROM {table}")
    return (await cur.fetchone())[0]


async def _evict_over_cap(table: str, order_col: str, cap: int) -> int:
    """cap dan oshган qatorlarni eng eski order_col bo'yicha o'chiradi."""
    total = await _count(table)
    excess = total - cap
    if excess <= 0:
        return 0
    await db().execute(
        f"""DELETE FROM {table} WHERE rowid IN (
                SELECT rowid FROM {table} ORDER BY {order_col} ASC LIMIT ?
            )""",
        (excess,),
    )
    return excess


def _db_size_mb() -> float:
    """DB + WAL + SHM umumiy hajmi (MB)."""
    path = db_path()
    total = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            total += os.path.getsize(path + suffix)
        except OSError:
            pass
    return total / (1024 * 1024)


async def run_once() -> None:
    started = time.monotonic()
    try:
        evicted_tc = await _evict_over_cap("track_cache", "last_used", TRACK_CACHE_MAX)
        evicted_rf = await _evict_over_cap("rec_features", "updated_at", REC_FEAT_MAX)
        cutoff = time.time() - REC_SHOWN_DAYS * 86400
        cur = await db().execute("DELETE FROM rec_shown WHERE shown_at < ?", (cutoff,))
        evicted_rs = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        await db().commit()

        # Bo'sh sahifalarni disk'ga qaytarish + WAL'ni asosiy faylga yig'ish
        await db().execute("PRAGMA incremental_vacuum")
        await db().execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await db().commit()

        size_mb = _db_size_mb()
        took = time.monotonic() - started
        log.info(
            "DB maintenance: %.1f MB | evicted track_cache=%d rec_features=%d "
            "rec_shown=%d | %.2fs",
            size_mb, evicted_tc, evicted_rf, evicted_rs, took,
        )
        if size_mb > 4096:  # 5 GB limitга yaqinlashuv
            log.warning("⚠️  DB hajmi %.0f MB — 5 GB limitга yaqin, cheklovlarни ko'rib chiqing", size_mb)
    except Exception:
        log.exception("DB maintenance xatosi")


async def loop() -> None:
    """main.py da background task sifatida ishga tushiriladi."""
    await asyncio.sleep(_FIRST_DELAY)
    while True:
        await run_once()
        await asyncio.sleep(_INTERVAL)
