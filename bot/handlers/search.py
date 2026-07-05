"""Matnli qidiruv — qo'shiq nomini yozish orqali topish."""

import html
import logging
from math import ceil

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot import keyboards, store, texts
from bot.services.spotify import SpotifyError, spotify

log = logging.getLogger(__name__)
router = Router(name="search")

PER_PAGE = 8


@router.message(F.text, ~F.text.startswith("/"))
async def text_search(message: Message) -> None:
    query = message.text.strip()[:100]
    status = await message.answer(texts.SEARCHING)
    try:
        tracks = await spotify.search(query)
    except SpotifyError:
        log.exception("Qidiruv xatosi: %s", query)
        await status.edit_text(texts.ERR_GENERIC)
        return
    if not tracks:
        await status.edit_text(texts.SEARCH_EMPTY.format(query=html.escape(query)))
        return
    store.remember_yt(tracks)
    token = store.stash_search(query, tracks)
    pages = ceil(len(tracks) / PER_PAGE)
    await status.edit_text(
        texts.SEARCH_RESULTS.format(query=html.escape(query), page=1, pages=pages),
        reply_markup=keyboards.search_results(tracks, token, 0, PER_PAGE),
    )


@router.callback_query(F.data.startswith("sr:"))
async def cb_search_page(cq: CallbackQuery) -> None:
    _, token, page_str = cq.data.split(":")
    item = store.searches.get(token)
    if item is None:
        await cq.answer(texts.ERR_EXPIRED, show_alert=True)
        return
    query, tracks = item
    page = int(page_str)
    pages = ceil(len(tracks) / PER_PAGE)
    await cq.answer()
    await cq.message.edit_text(
        texts.SEARCH_RESULTS.format(query=html.escape(query), page=page + 1, pages=pages),
        reply_markup=keyboards.search_results(tracks, token, page, PER_PAGE),
    )
