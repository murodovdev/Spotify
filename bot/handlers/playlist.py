"""Interaktiv playlist brauzeri.

Playlist havolasi kelganda barcha treklarni ketma-ket yuborish o'rniga
musiqa ilovasidek sahifalangan menyu ko'rsatiladi: qo'shiqni tanlansa faqat
o'sha trek yuklanadi, menyu esa joyida qoladi. Qo'shimcha: tasodifiy tanlash,
ommaboplik bo'yicha saralash va playlist ichida qidiruv.
"""

import logging
import random

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from bot import keyboards, store
from bot.i18n import Texts, playlist_header
from bot.services import queue
from bot.services.spotify import Playlist, SpotifyError, spotify

log = logging.getLogger(__name__)
router = Router(name="playlist")

PER_PAGE = 12


def _ordered(playlist: Playlist, sort_pop: bool) -> list:
    if sort_pop:
        return sorted(playlist.tracks, key=lambda tr: tr.popularity, reverse=True)
    return playlist.tracks


def _pages(count: int) -> int:
    return max(1, (count + PER_PAGE - 1) // PER_PAGE)


async def _render(
    message: Message, playlist: Playlist, token: str, page: int, sort_pop: bool, t: Texts
) -> None:
    """Brauzer xabarini yangilaydi (rasm izohi yoki matn — turiga qarab)."""
    tracks = _ordered(playlist, sort_pop)
    has_pop = any(tr.popularity for tr in playlist.tracks)
    pages = _pages(len(tracks))
    page = max(0, min(page, pages - 1))
    text = playlist_header(playlist, page, pages, t)
    markup = keyboards.playlist_browser(
        token, tracks, page, t, PER_PAGE, sort_pop, has_pop
    )
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=markup)
        else:
            await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass


async def _send_browser(bot: Bot, chat_id: int, playlist: Playlist, t: Texts) -> None:
    """Yangi playlist brauzerini yuboradi (muqova bo'lsa rasm bilan)."""
    store.remember(playlist.tracks)
    token = store.stash_playlist(playlist)
    tracks = _ordered(playlist, False)
    has_pop = any(tr.popularity for tr in playlist.tracks)
    pages = _pages(len(tracks))
    text = playlist_header(playlist, 0, pages, t)
    markup = keyboards.playlist_browser(token, tracks, 0, t, PER_PAGE, False, has_pop)
    if playlist.cover_url:
        try:
            await bot.send_photo(
                chat_id, playlist.cover_url, caption=text, reply_markup=markup
            )
            return
        except TelegramBadRequest:
            pass  # muqova yuborilmasa matnga o'tamiz
    await bot.send_message(chat_id, text, reply_markup=markup)


async def open_from_link(bot: Bot, chat_id: int, sid: str, t: Texts) -> None:
    """Playlist havolasidan interaktiv brauzerni ochadi."""
    status = await bot.send_message(chat_id, t.FETCHING_INFO)
    try:
        playlist = await spotify.playlist_info(sid)
    except SpotifyError:
        log.exception("Playlist metadata xatosi: %s", sid)
        await status.edit_text(t.ERR_GENERIC)
        return
    if not playlist.tracks:
        await status.edit_text(t.ERR_GENERIC)
        return
    await status.delete()
    await _send_browser(bot, chat_id, playlist, t)


def _get(token: str) -> Playlist | None:
    item = store.playlists.get(token)
    if item is not None:
        store.playlists.move_to_end(token)
    return item


@router.callback_query(F.data == "pl:nop")
async def cb_noop(cq: CallbackQuery) -> None:
    await cq.answer()


@router.callback_query(F.data == "pl:x")
async def cb_close(cq: CallbackQuery) -> None:
    store.playlist_search_mode.pop(cq.from_user.id, None)
    await cq.answer()
    try:
        await cq.message.delete()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("pl:p:"))
async def cb_page(cq: CallbackQuery, t: Texts) -> None:
    _, _, token, page_str, sort_str = cq.data.split(":")
    playlist = _get(token)
    if playlist is None:
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return
    await cq.answer()
    await _render(cq.message, playlist, token, int(page_str), sort_str == "1", t)


@router.callback_query(F.data.startswith("pl:sh:"))
async def cb_shuffle(cq: CallbackQuery, t: Texts) -> None:
    token = cq.data.split(":", 2)[2]
    playlist = _get(token)
    if playlist is None:
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return
    track = random.choice(playlist.tracks)
    await cq.answer(f"🎲 {track.full_name}"[:200])
    await queue.process_single(cq.bot, cq.message.chat.id, cq.from_user.id, track.id, t)


@router.callback_query(F.data.startswith("pl:s:"))
async def cb_search_prompt(cq: CallbackQuery, t: Texts) -> None:
    token = cq.data.split(":", 2)[2]
    if _get(token) is None:
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return
    store.playlist_search_mode[cq.from_user.id] = token
    await cq.answer()
    await cq.message.answer(t.PL_SEARCH_PROMPT)


def _in_search_mode(message: Message) -> bool:
    return message.from_user.id in store.playlist_search_mode


@router.message(F.text, ~F.text.startswith("/"), _in_search_mode)
async def playlist_text_search(message: Message, t: Texts) -> None:
    """Playlist ichida qidiruv — 🔎 tugmasidan keyingi matnli xabar."""
    token = store.playlist_search_mode.pop(message.from_user.id, None)
    playlist = _get(token) if token else None
    if playlist is None:
        await message.answer(t.ERR_EXPIRED)
        return
    query = message.text.strip()[:100]
    q = query.casefold()
    matches = [
        tr
        for tr in playlist.tracks
        if q in tr.title.casefold() or q in tr.artists.casefold()
    ]
    if not matches:
        await message.answer(t.PL_SEARCH_EMPTY)
        return
    result = Playlist(
        title=t.PL_SEARCH_TITLE.format(query=query),
        creator=playlist.creator,
        total=len(matches),
        cover_url="",
        tracks=matches,
    )
    await _send_browser(message.bot, message.chat.id, result, t)
