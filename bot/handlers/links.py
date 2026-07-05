"""Spotify havolalari va yuklab olish callback'lari."""

import html
import logging
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot import keyboards, store, texts
from bot.services import queue
from bot.services.spotify import SpotifyError, spotify

log = logging.getLogger(__name__)
router = Router(name="links")

LINK_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[\w-]+/)?(track|album|playlist|artist)/([A-Za-z0-9]+)"
)
URI_RE = re.compile(r"spotify:(track|album|playlist|artist):([A-Za-z0-9]+)")

# Shundan ko'p trekli to'plamlar uchun avval tasdiq so'raladi
CONFIRM_THRESHOLD = 30


def _extract(text: str):
    return LINK_RE.search(text) or URI_RE.search(text)


async def start_or_confirm(bot, chat_id: int, user_id: int, title: str, tracks, status: Message) -> None:
    """Kichik to'plamni darhol boshlaydi, kattasiga tasdiq so'raydi."""
    if not tracks:
        await status.edit_text(texts.ERR_GENERIC)
        return
    if len(tracks) <= CONFIRM_THRESHOLD:
        await status.delete()
        await queue.process_collection(bot, chat_id, user_id, title, tracks)
        return
    token = store.stash_collection(user_id, title, tracks)
    await status.edit_text(
        texts.CONFIRM_COLLECTION.format(title=html.escape(title), count=len(tracks)),
        reply_markup=keyboards.confirm_collection(token),
    )


async def _handle_collection(bot, chat_id: int, user_id: int, kind: str, sid: str) -> None:
    status = await bot.send_message(chat_id, texts.FETCHING_INFO)
    try:
        if kind == "album":
            title, tracks = await spotify.album(sid)
        elif kind == "playlist":
            title, tracks = await spotify.playlist(sid)
        else:  # artist
            name, tracks = await spotify.artist_top(sid)
            title = f"{name} — Top treklar"
    except SpotifyError:
        log.exception("Spotify metadata xatosi: %s %s", kind, sid)
        await status.edit_text(texts.ERR_GENERIC)
        return
    await start_or_confirm(bot, chat_id, user_id, title, tracks, status)


@router.message(F.text.func(lambda t: bool(_extract(t))))
async def handle_link(message: Message) -> None:
    kind, sid = _extract(message.text).groups()
    user_id = message.from_user.id
    if kind == "track":
        await queue.process_single(message.bot, message.chat.id, user_id, sid)
    else:
        await _handle_collection(message.bot, message.chat.id, user_id, kind, sid)


@router.callback_query(F.data.startswith("dl:"))
async def cb_download(cq: CallbackQuery) -> None:
    _, kind, sid = cq.data.split(":", 2)
    user_id = cq.from_user.id
    chat_id = cq.message.chat.id
    await cq.answer()
    if kind == "t":
        await queue.process_single(cq.bot, chat_id, user_id, sid)
    elif kind == "a":
        await _handle_collection(cq.bot, chat_id, user_id, "album", sid)
    elif kind == "ar":
        await _handle_collection(cq.bot, chat_id, user_id, "artist", sid)


@router.callback_query(F.data.startswith("go:"))
async def cb_confirm_go(cq: CallbackQuery) -> None:
    token = cq.data[3:]
    item = store.pending_collections.pop(token, None)
    if item is None:
        await cq.answer(texts.ERR_EXPIRED, show_alert=True)
        return
    owner_id, title, tracks = item
    if cq.from_user.id != owner_id:
        store.pending_collections[token] = item
        await cq.answer(texts.ERR_EXPIRED, show_alert=True)
        return
    await cq.answer()
    await cq.message.delete()
    await queue.process_collection(cq.bot, cq.message.chat.id, owner_id, title, tracks)


@router.callback_query(F.data.startswith("no:"))
async def cb_confirm_no(cq: CallbackQuery) -> None:
    store.pending_collections.pop(cq.data[3:], None)
    await cq.answer()
    await cq.message.delete()


@router.callback_query(F.data.startswith("stop:"))
async def cb_stop(cq: CallbackQuery) -> None:
    owner_id = int(cq.data.split(":")[1])
    if cq.from_user.id != owner_id:
        await cq.answer()
        return
    if queue.manager.cancel(owner_id):
        await cq.answer("⏹ Bekor qilinmoqda…")
    else:
        await cq.answer()
