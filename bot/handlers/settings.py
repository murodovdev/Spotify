"""Sozlamalar va admin statistikasi."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import keyboards
from bot.config import settings as cfg
from bot.db import repo
from bot.i18n import LANG_LABELS, Texts, get_texts

router = Router(name="settings")


async def _settings_msg(user_id: int, t: Texts, lang: str | None):
    quality = await repo.get_quality(user_id)
    return t.SETTINGS.format(quality=quality), keyboards.settings_kb(quality, lang or "uz", t)


@router.message(Command("settings"))
async def cmd_settings(message: Message, t: Texts, lang: str | None) -> None:
    text, kb = await _settings_msg(message.from_user.id, t, lang)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:settings")
async def cb_settings(cq: CallbackQuery, t: Texts, lang: str | None) -> None:
    await cq.answer()
    text, kb = await _settings_msg(cq.from_user.id, t, lang)
    await cq.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("q:"))
async def cb_quality(cq: CallbackQuery, t: Texts, lang: str | None) -> None:
    quality = cq.data.split(":")[1]
    if quality not in ("128", "320"):
        await cq.answer()
        return
    await repo.set_quality(cq.from_user.id, quality)
    await cq.answer(t.QUALITY_SET.format(quality=quality))
    text, kb = await _settings_msg(cq.from_user.id, t, lang)
    try:
        await cq.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data == "menu:lang")
async def cb_lang_menu(cq: CallbackQuery, t: Texts) -> None:
    await cq.answer()
    await cq.message.edit_text(
        t.CHOOSE_LANG,
        reply_markup=keyboards.lang_picker("setlang"),
    )


@router.callback_query(F.data.startswith("setlang:"))
async def cb_set_lang(cq: CallbackQuery) -> None:
    new_lang = cq.data.split(":")[1]
    if new_lang not in LANG_LABELS:
        await cq.answer()
        return
    await repo.set_lang(cq.from_user.id, new_lang)
    t = get_texts(new_lang)
    await cq.answer(t.LANG_SET)
    text, kb = await _settings_msg(cq.from_user.id, t, new_lang)
    try:
        await cq.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


@router.message(Command("stats"))
async def cmd_stats(message: Message, t: Texts) -> None:
    if cfg.admin_id and message.from_user.id != cfg.admin_id:
        return
    stats = await repo.get_stats()
    await message.answer(t.STATS.format(**stats))
