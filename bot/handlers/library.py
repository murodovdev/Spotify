"""Spotify hisobini ulash va Liked Songs yuklab olish."""

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import keyboards, texts
from bot.db import repo
from bot.security import sign_state
from bot.services import queue
from bot.services.spotify import NotConnected, SpotifyError, spotify

log = logging.getLogger(__name__)
router = Router(name="library")


async def _send_connect_prompt(bot: Bot, chat_id: int, user_id: int, prefix: str = "") -> None:
    auth_url = spotify.auth_url(sign_state(user_id))
    text = f"{prefix}\n\n{texts.CONNECT_PROMPT}" if prefix else texts.CONNECT_PROMPT
    await bot.send_message(
        chat_id, text, reply_markup=keyboards.connect_button(auth_url)
    )


@router.callback_query(F.data == "menu:connect")
async def cb_connect(cq: CallbackQuery) -> None:
    await cq.answer()
    if not spotify.has_credentials:
        await cq.message.answer(texts.ERR_NO_CREDENTIALS)
        return
    if await repo.is_connected(cq.from_user.id):
        await cq.message.answer(texts.ALREADY_CONNECTED)
        return
    await _send_connect_prompt(cq.bot, cq.message.chat.id, cq.from_user.id)


@router.callback_query(F.data == "menu:disconnect")
async def cb_disconnect(cq: CallbackQuery) -> None:
    await repo.delete_tokens(cq.from_user.id)
    await cq.answer()
    await cq.message.answer(texts.DISCONNECTED)


async def _liked_entry(bot: Bot, chat_id: int, user_id: int) -> None:
    if not spotify.has_credentials:
        await bot.send_message(chat_id, texts.ERR_NO_CREDENTIALS)
        return
    if not await repo.is_connected(user_id):
        await _send_connect_prompt(bot, chat_id, user_id, prefix=texts.NOT_CONNECTED)
        return
    status = await bot.send_message(chat_id, texts.LIKED_FETCHING)
    try:
        count = await spotify.liked_count(user_id)
    except NotConnected:
        await status.delete()
        await _send_connect_prompt(bot, chat_id, user_id, prefix=texts.NOT_CONNECTED)
        return
    except SpotifyError as e:
        log.exception("Liked count xatosi")
        if "403" in str(e):
            await status.edit_text(texts.ERR_PREMIUM)
        else:
            await status.edit_text(texts.ERR_GENERIC)
        return
    if count == 0:
        await status.edit_text(texts.LIKED_EMPTY)
        return
    await status.edit_text(
        texts.LIKED_CONFIRM.format(count=count),
        reply_markup=keyboards.confirm_collection("liked"),
    )


@router.message(Command("liked"))
async def cmd_liked(message: Message) -> None:
    await _liked_entry(message.bot, message.chat.id, message.from_user.id)


@router.callback_query(F.data == "menu:liked")
async def cb_liked(cq: CallbackQuery) -> None:
    await cq.answer()
    await _liked_entry(cq.bot, cq.message.chat.id, cq.from_user.id)


@router.callback_query(F.data == "go:liked")
async def cb_liked_go(cq: CallbackQuery) -> None:
    user_id = cq.from_user.id
    await cq.answer()
    try:
        await cq.message.edit_text(texts.LIKED_FETCHING)
        tracks = await spotify.liked_tracks(user_id)
    except (NotConnected, SpotifyError) as e:
        log.exception("Liked tracks xatosi")
        if "403" in str(e):
            await cq.message.edit_text(texts.ERR_PREMIUM)
        else:
            await cq.message.edit_text(texts.ERR_GENERIC)
        return
    await cq.message.delete()
    await queue.process_collection(
        cq.bot, cq.message.chat.id, user_id, "❤️ Liked Songs", tracks
    )


@router.callback_query(F.data == "no:liked")
async def cb_liked_no(cq: CallbackQuery) -> None:
    await cq.answer()
    await cq.message.delete()
