"""Matnli qidiruv — qo'shiq nomini yozish orqali topish."""

import html
import logging
from math import ceil

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot import keyboards, store
from bot.admin import repo as admin_repo
from bot.admin import settings_store
from bot.i18n import Texts
from bot.services import search_engine

log = logging.getLogger(__name__)
router = Router(name="search")

PER_PAGE = 6


@router.message(F.text, ~F.text.startswith("/"))
async def text_search(message: Message, t: Texts) -> None:
    if not settings_store.feature_enabled("search"):
        await message.answer("🔍 Search is temporarily disabled.")
        return
    query = message.text.strip()[:100]
    status = await message.answer(t.SEARCHING)
    try:
        tracks = await search_engine.search(query)
    except Exception:
        log.exception("Qidiruv xatosi: %s", query)
        await status.edit_text(t.ERR_GENERIC)
        return
    if not tracks:
        try:
            await admin_repo.add_failed("search", query)
        except Exception:
            pass
        await status.edit_text(t.SEARCH_EMPTY.format(query=html.escape(query)))
        return
    try:
        top = tracks[0]
        await admin_repo.bump_song(
            f"{(top.artists or '').strip().lower()} — {(top.title or '').strip().lower()}"[:200],
            top.title or "", top.artists or "", "searches",
        )
    except Exception:
        pass
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
