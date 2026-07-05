"""Sozlamalar, tarix va admin statistikasi."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import keyboards, texts
from bot.config import settings as cfg
from bot.db import repo

router = Router(name="settings")


async def _settings_text(user_id: int) -> tuple[str, object]:
    quality = await repo.get_quality(user_id)
    return texts.SETTINGS.format(quality=quality), keyboards.settings_kb(quality)


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    text, kb = await _settings_text(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:settings")
async def cb_settings(cq: CallbackQuery) -> None:
    await cq.answer()
    text, kb = await _settings_text(cq.from_user.id)
    await cq.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("q:"))
async def cb_quality(cq: CallbackQuery) -> None:
    quality = cq.data.split(":")[1]
    if quality not in ("128", "320"):
        await cq.answer()
        return
    await repo.set_quality(cq.from_user.id, quality)
    await cq.answer(texts.QUALITY_SET.format(quality=quality))
    text, kb = await _settings_text(cq.from_user.id)
    try:
        await cq.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


async def _history(message_target, user_id: int) -> None:
    items = await repo.get_history(user_id)
    if not items:
        await message_target.answer(texts.HISTORY_EMPTY)
        return
    await message_target.answer(
        texts.HISTORY_TITLE, reply_markup=keyboards.history_kb(items)
    )


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    await _history(message, message.from_user.id)


@router.callback_query(F.data == "menu:history")
async def cb_history(cq: CallbackQuery) -> None:
    await cq.answer()
    await _history(cq.message, cq.from_user.id)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if cfg.admin_id and message.from_user.id != cfg.admin_id:
        return
    stats = await repo.get_stats()
    await message.answer(texts.STATS.format(**stats))
