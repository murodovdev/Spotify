"""force_subs jadvali uchun CRUD. Biznes mantiq yo'q — u services/forcesub.py da."""

from __future__ import annotations

from bot.db.database import db


async def list_all() -> list:
    """Barcha yozuvlar (o'chirilganlari ham) — admin paneli uchun."""
    cur = await db().execute(
        "SELECT * FROM force_subs ORDER BY sort_order, chat_id"
    )
    return await cur.fetchall()


async def list_enabled() -> list:
    cur = await db().execute(
        "SELECT * FROM force_subs WHERE enabled=1 ORDER BY sort_order, chat_id"
    )
    return await cur.fetchall()


async def get(chat_id: int):
    cur = await db().execute("SELECT * FROM force_subs WHERE chat_id=?", (chat_id,))
    return await cur.fetchone()


async def add(
    chat_id: int, username: str | None, title: str, kind: str, invite_link: str | None
) -> None:
    """Qo'shadi yoki mavjudini yangilaydi (sort_order va enabled saqlanadi)."""
    cur = await db().execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM force_subs")
    next_order = (await cur.fetchone())["n"]
    await db().execute(
        """INSERT INTO force_subs(chat_id, username, title, kind, invite_link, enabled, sort_order)
           VALUES(?,?,?,?,?,1,?)
           ON CONFLICT(chat_id) DO UPDATE SET
               username=excluded.username,
               title=excluded.title,
               kind=excluded.kind,
               invite_link=excluded.invite_link""",
        (chat_id, username, title, kind, invite_link, next_order),
    )
    await db().commit()


async def remove(chat_id: int) -> None:
    await db().execute("DELETE FROM force_subs WHERE chat_id=?", (chat_id,))
    await db().commit()


async def set_enabled(chat_id: int, enabled: bool) -> None:
    await db().execute(
        "UPDATE force_subs SET enabled=? WHERE chat_id=?", (1 if enabled else 0, chat_id)
    )
    await db().commit()


async def move(chat_id: int, direction: int) -> bool:
    """Tartibda bir pog'ona yuqoriga (-1) yoki pastga (+1) suradi.

    Ikki yozuvning `sort_order`ini almashtirish yetarli emas: qolgan yozuvlarda
    qiymatlar ixtiyoriy (yoki takrorlanuvchi) bo'lishi mumkin. Shu sabab ro'yxat
    joriy ko'rinishi bo'yicha qayta raqamlanadi — natija har doim barqaror.
    """
    rows = list(await list_all())
    idx = next((i for i, r in enumerate(rows) if r["chat_id"] == chat_id), None)
    if idx is None:
        return False
    swap = idx + direction
    if not (0 <= swap < len(rows)):
        return False

    rows[idx], rows[swap] = rows[swap], rows[idx]
    await db().executemany(
        "UPDATE force_subs SET sort_order=? WHERE chat_id=?",
        [(i, r["chat_id"]) for i, r in enumerate(rows)],
    )
    await db().commit()
    return True
