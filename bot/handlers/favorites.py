"""Sevimlilar: qo'shiq ostidagi 🤍/❤️ tugmasi va /favorites ro'yxati."""

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot import keyboards
from bot.db import repo
from bot.i18n import Texts

router = Router(name="favorites")


@router.callback_query(F.data.startswith("fav:"))
async def cb_fav_toggle(cq: CallbackQuery, t: Texts) -> None:
    track_id = cq.data[4:]
    row = await repo.cache_any_row(track_id)
    title = (row["title"] if row else "") or ""
    artist = (row["artist"] if row else "") or ""
    saved = await repo.toggle_favorite(cq.from_user.id, track_id, title, artist)
    await cq.answer(t.FAV_ADDED if saved else t.FAV_REMOVED)

    # Faqat shu tugmaning yozuvini o'zgartiramiz — qolgan tugmalar joyida qoladi.
    markup = cq.message.reply_markup if cq.message else None
    if not markup:
        return
    new_label = t.BTN_FAV_SAVED if saved else t.BTN_FAV_ADD
    new_rows = [
        [
            InlineKeyboardButton(text=new_label, callback_data=b.callback_data)
            if b.callback_data == cq.data
            else b
            for b in row_
        ]
        for row_ in markup.inline_keyboard
    ]
    try:
        await cq.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=new_rows)
        )
    except Exception:
        pass


async def _favorites_entry(bot: Bot, chat_id: int, user_id: int, t: Texts) -> None:
    rows = await repo.list_favorites(user_id)
    if not rows:
        await bot.send_message(chat_id, t.FAV_EMPTY)
        return
    await bot.send_message(
        chat_id, t.FAV_TITLE, reply_markup=keyboards.favorites_list(rows, t)
    )


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, t: Texts) -> None:
    await _favorites_entry(message.bot, message.chat.id, message.from_user.id, t)


@router.callback_query(F.data == "menu:favorites")
async def cb_favorites(cq: CallbackQuery, t: Texts) -> None:
    await cq.answer()
    await _favorites_entry(cq.bot, cq.message.chat.id, cq.from_user.id, t)
