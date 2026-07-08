"""Majburiy obuna ekrani va "✅ Qo'shildim" tekshiruvi.

Ekranning o'zi middleware'da (bot/main.py) ko'rsatiladi — bu router faqat
tugma bosilishini qayta ishlaydi. `fs:check` callback'i middleware gate'idan
ataylab ozod: aks holda foydalanuvchi hech qachon o'zini tekshira olmasdi.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from bot import keyboards
from bot.db import repo
from bot.handlers.start import welcome_text
from bot.i18n import Texts
from bot.services import forcesub

log = logging.getLogger(__name__)
router = Router(name="forcesub")


async def send_screen(bot: Bot, chat_id: int, t: Texts) -> None:
    await bot.send_message(
        chat_id, t.FS_TITLE, reply_markup=keyboards.force_sub(forcesub.chats(), t)
    )


@router.callback_query(F.data == "fs:check")
async def cb_check(cq: CallbackQuery, t: Texts, bot: Bot) -> None:
    # Tugma bosilishiga ishonmaymiz — keshni chetlab o'tib Telegram'dan so'raymiz.
    missing = await forcesub.verify(bot, cq.from_user.id)

    if missing:
        names = ", ".join(c["title"] for c in missing[:3])
        if len(missing) > 3:
            names += f" (+{len(missing) - 3})"
        await cq.answer(t.FS_STILL_MISSING.format(chats=names), show_alert=True)
        return

    await cq.answer(t.FS_JOINED)
    # Obuna ekranini olib tashlab, oddiy welcome bilan almashtiramiz — ortiqcha
    # xabar qoldirmaymiz.
    try:
        await cq.message.delete()
    except Exception:
        pass
    connected = await repo.is_connected(cq.from_user.id)
    await cq.message.answer(
        welcome_text(t, cq.from_user.first_name),
        reply_markup=keyboards.main_menu(connected, t),
    )
