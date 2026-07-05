"""Matnli qidiruv — qo'shiq nomini yozish orqali topish."""

import html
import logging
from math import ceil

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot import keyboards, store
from bot.i18n import Texts
from bot.services import search_engine

log = logging.getLogger(__name__)
router = Router(name="search")

PER_PAGE = 6


@router.message(F.text, ~F.text.startswith("/"))
async def text_search(message: Message, t: Texts) -> None:
    query = message.text.strip()[:100]
    status = await message.answer(t.SEARCHING)
    try:
        tracks = await search_engine.search(query)
    except Exception:
        log.exception("Qidiruv xatosi: %s", query)
        await status.edit_text(t.ERR_GENERIC)
        return
    if not tracks:
        await status.edit_text(t.SEARCH_EMPTY.format(query=html.escape(query)))
        return
    store.remember(tracks)
    token = store.stash_search(query, tracks)
    pages = ceil(len(tracks) / PER_PAGE)
    await status.edit_text(
        t.SEARCH_RESULTS.format(query=html.escape(query), page=1, pages=pages),
        reply_markup=keyboards.search_results(tracks, token, 0, t, PER_PAGE),
    )


@router.callback_query(F.data.startswith("sr:"))
async def cb_search_page(cq: CallbackQuery, t: Texts) -> None:
    _, token, page_str = cq.data.split(":")
    item = store.searches.get(token)
    if item is None:
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return
    query, tracks = item
    page = int(page_str)
    pages = ceil(len(tracks) / PER_PAGE)
    await cq.answer()
    await cq.message.edit_text(
        t.SEARCH_RESULTS.format(query=html.escape(query), page=page + 1, pages=pages),
        reply_markup=keyboards.search_results(tracks, token, page, t, PER_PAGE),
    )
