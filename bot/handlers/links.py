"""Spotify havolalari va yuklab olish callback'lari."""

import html
import logging
import random
import re
from math import ceil

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from bot import keyboards, store
from bot.db import repo
from bot.i18n import Texts
from bot.services import queue
from bot.services.spotify import Playlist, SpotifyError, Track, spotify

log = logging.getLogger(__name__)
router = Router(name="links")

LINK_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[\w-]+/)?(track|album|playlist|artist)/([A-Za-z0-9]+)"
)
URI_RE = re.compile(r"spotify:(track|album|playlist|artist):([A-Za-z0-9]+)")

CONFIRM_THRESHOLD = 30
PLAYLIST_PER_PAGE = 10


def _extract(text: str):
    return LINK_RE.search(text) or URI_RE.search(text)


async def start_or_confirm(bot, chat_id: int, user_id: int, title: str, tracks, status: Message, t: Texts) -> None:
    if not tracks:
        await status.edit_text(t.ERR_GENERIC)
        return
    if len(tracks) <= CONFIRM_THRESHOLD:
        await status.delete()
        await queue.process_collection(bot, chat_id, user_id, title, tracks, t)
        return
    token = store.stash_collection(user_id, title, tracks)
    await status.edit_text(
        t.CONFIRM_COLLECTION.format(title=html.escape(title), count=len(tracks)),
        reply_markup=keyboards.confirm_collection(token, t),
    )


def _popular_first(tracks: list[Track]) -> list[Track]:
    if not any(track.popularity for track in tracks):
        return tracks
    return sorted(tracks, key=lambda track: track.popularity, reverse=True)


def _clip(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _duration(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    return f"{mins}:{secs:02d}"


def _track_item_line(number: int, track: Track) -> str:
    parts = []
    if track.artists:
        parts.append(f"👤 {html.escape(_clip(track.artists, 12))}")
    if track.duration:
        parts.append(f"⏱ {_duration(track.duration)}")
    if track.album:
        parts.append(f"💿 {html.escape(_clip(track.album, 12))}")
    if track.year:
        parts.append(f"📅 {html.escape(track.year)}")
    title = html.escape(_clip(track.title or "Track", 16))
    meta = " · ".join(parts)
    suffix = f" · {meta}" if meta else ""
    return f"{number}. 🎵 <b>{title}</b>{suffix}"


def _playlist_pages(session: store.PlaylistSession) -> int:
    return max(1, ceil(len(session.view_tracks) / PLAYLIST_PER_PAGE))


def _playlist_message(session: store.PlaylistSession, page: int, t: Texts) -> str:
    pages = _playlist_pages(session)
    start = page * PLAYLIST_PER_PAGE
    shown = session.view_tracks[start : start + PLAYLIST_PER_PAGE]
    items = "\n".join(
        _track_item_line(index + 1, track)
        for index, track in enumerate(shown, start=start)
    )
    if not items:
        if session.mode == "search":
            items = t.PLAYLIST_SEARCH_EMPTY.format(query=html.escape(session.query))
        else:
            items = t.PLAYLIST_EMPTY

    creator_line = ""
    if session.creator:
        creator_line = f"👤 {html.escape(_clip(session.creator, 32))}\n"

    mode_line = ""
    if session.mode == "search":
        mode_line = t.PLAYLIST_SEARCH_RESULTS.format(query=html.escape(session.query))
    elif session.mode == "favorites":
        mode_line = f"{t.BTN_PLAYLIST_FAVS}: <b>{len(session.view_tracks)}</b>\n"

    return t.PLAYLIST_HEADER.format(
        title=html.escape(_clip(session.title, 48)),
        creator_line=creator_line,
        count=session.total,
        mode_line=mode_line,
        page=page + 1,
        pages=pages,
        items=items,
    )


def _playlist_markup(session: store.PlaylistSession, token: str, page: int, t: Texts):
    return keyboards.playlist_browser(
        session.view_tracks,
        token,
        page,
        _playlist_pages(session),
        t,
        PLAYLIST_PER_PAGE,
        favorites_mode=session.mode == "favorites",
    )


async def _edit_playlist_message(
    bot,
    chat_id: int,
    session: store.PlaylistSession,
    token: str,
    page: int,
    t: Texts,
) -> None:
    text = _playlist_message(session, page, t)
    markup = _playlist_markup(session, token, page, t)
    try:
        if session.has_cover:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=session.message_id,
                caption=text,
                reply_markup=markup,
            )
        else:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=session.message_id,
                text=text,
                reply_markup=markup,
            )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise


async def _show_playlist(
    bot,
    chat_id: int,
    user_id: int,
    playlist: Playlist,
    status: Message,
    t: Texts,
) -> None:
    if not playlist.tracks:
        await status.edit_text(t.PLAYLIST_EMPTY)
        return

    playlist.cover_url = playlist.cover_url or playlist.tracks[0].cover_url
    token = store.stash_playlist(user_id, playlist, _popular_first(playlist.tracks))
    session = store.playlists[token]
    text = _playlist_message(session, 0, t)
    markup = _playlist_markup(session, token, 0, t)

    if playlist.cover_url:
        try:
            msg = await bot.send_photo(
                chat_id,
                photo=playlist.cover_url,
                caption=text,
                reply_markup=markup,
            )
            try:
                await status.delete()
            except Exception:
                pass
            session.message_id = msg.message_id
            session.has_cover = True
            return
        except Exception:
            log.exception("Playlist cover yuborilmadi, matnli ko'rinishga o'tildi")

    await status.edit_text(text, reply_markup=markup)
    session.message_id = status.message_id
    session.has_cover = False


async def _handle_collection(bot, chat_id: int, user_id: int, kind: str, sid: str, t: Texts) -> None:
    status = await bot.send_message(chat_id, t.FETCHING_INFO)
    try:
        if kind == "album":
            title, tracks = await spotify.album(sid)
        elif kind == "playlist":
            playlist = await spotify.playlist(sid)
            await _show_playlist(bot, chat_id, user_id, playlist, status, t)
            return
        else:
            name, tracks = await spotify.artist_top(sid)
            title = f"{name} — Top"
    except SpotifyError:
        log.exception("Spotify metadata xatosi: %s %s", kind, sid)
        await status.edit_text(t.ERR_GENERIC)
        return
    await start_or_confirm(bot, chat_id, user_id, title, tracks, status, t)


@router.message(F.text, F.from_user.id.func(lambda user_id: user_id in store.pending_playlist_searches))
async def playlist_search(message: Message, t: Texts) -> None:
    user_id = message.from_user.id
    token = store.pending_playlist_searches.pop(user_id, None)
    session = store.playlists.get(token or "")
    if session is None or session.user_id != user_id:
        await message.answer(t.ERR_EXPIRED)
        return

    query = message.text.strip()[:80]
    needle = query.casefold()
    session.mode = "search"
    session.query = query
    session.view_tracks = [
        track
        for track in session.tracks
        if needle in " ".join(
            [
                track.title,
                track.artists,
                track.album,
                track.year,
            ]
        ).casefold()
    ]
    if any(track.popularity for track in session.view_tracks):
        session.view_tracks = _popular_first(session.view_tracks)

    try:
        await _edit_playlist_message(message.bot, message.chat.id, session, token, 0, t)
    except Exception:
        log.exception("Playlist qidiruv natijasini yangilashda xato")
        await message.answer(t.PLAYLIST_SEARCH_EMPTY.format(query=html.escape(query)))

    try:
        await message.delete()
    except Exception:
        pass


@router.message(F.text.func(lambda txt: bool(_extract(txt))))
async def handle_link(message: Message, t: Texts) -> None:
    kind, sid = _extract(message.text).groups()
    user_id = message.from_user.id
    if kind == "track":
        await queue.process_single(message.bot, message.chat.id, user_id, sid, t)
    else:
        await _handle_collection(message.bot, message.chat.id, user_id, kind, sid, t)


@router.callback_query(F.data.startswith("dl:"))
async def cb_download(cq: CallbackQuery, t: Texts) -> None:
    _, kind, sid = cq.data.split(":", 2)
    user_id = cq.from_user.id
    chat_id = cq.message.chat.id
    await cq.answer()
    if kind == "t":
        await queue.process_single(cq.bot, chat_id, user_id, sid, t)
    elif kind == "a":
        await _handle_collection(cq.bot, chat_id, user_id, "album", sid, t)
    elif kind == "ar":
        await _handle_collection(cq.bot, chat_id, user_id, "artist", sid, t)


@router.callback_query(F.data.startswith("pl:"))
async def cb_playlist(cq: CallbackQuery, t: Texts) -> None:
    parts = cq.data.split(":")
    if len(parts) < 3:
        await cq.answer()
        return

    token = parts[1]
    action = parts[2]
    session = store.playlists.get(token)
    user_id = cq.from_user.id
    if session is None or session.user_id != user_id:
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return

    chat_id = cq.message.chat.id

    if action == "p" and len(parts) == 4:
        page = max(0, min(int(parts[3]), _playlist_pages(session) - 1))
        await cq.answer()
        await _edit_playlist_message(cq.bot, chat_id, session, token, page, t)
        return

    if action == "search":
        store.remember_playlist_search(user_id, token)
        await cq.answer(t.PLAYLIST_SEARCH_PROMPT, show_alert=True)
        return

    if action == "shuffle":
        if not session.view_tracks:
            await cq.answer(t.PLAYLIST_EMPTY, show_alert=True)
            return
        track = random.choice(session.view_tracks)
        await cq.answer(f"🎲 {_clip(track.title, 60)}")
        await queue.process_single(cq.bot, chat_id, user_id, track.id, t)
        return

    if action == "t" and len(parts) == 4:
        idx = int(parts[3])
        if idx < 0 or idx >= len(session.view_tracks):
            await cq.answer(t.ERR_EXPIRED, show_alert=True)
            return
        track = session.view_tracks[idx]
        await cq.answer()
        await queue.process_single(cq.bot, chat_id, user_id, track.id, t)
        return

    if action == "fav":
        rows = await repo.list_favorites(user_id, limit=500)
        favorite_ids = {row["spotify_id"] for row in rows}
        favorite_tracks = [track for track in session.tracks if track.id in favorite_ids]
        if not favorite_tracks:
            await cq.answer(t.PLAYLIST_NO_FAVORITES, show_alert=True)
            return
        session.mode = "favorites"
        session.query = ""
        session.view_tracks = _popular_first(favorite_tracks)
        await cq.answer()
        await _edit_playlist_message(cq.bot, chat_id, session, token, 0, t)
        return

    if action == "all":
        session.mode = "all"
        session.query = ""
        session.view_tracks = _popular_first(session.tracks)
        await cq.answer()
        await _edit_playlist_message(cq.bot, chat_id, session, token, 0, t)
        return

    if action == "back":
        store.playlists.pop(token, None)
        await cq.answer()
        try:
            await cq.message.delete()
        except Exception:
            pass
        connected = await repo.is_connected(user_id)
        name = html.escape((cq.from_user.first_name or "").strip()) or "🎧"
        await cq.message.answer(
            t.WELCOME.format(name=name),
            reply_markup=keyboards.main_menu(connected, t),
        )
        return

    await cq.answer()


@router.callback_query(F.data.startswith("go:"))
async def cb_confirm_go(cq: CallbackQuery, t: Texts) -> None:
    token = cq.data[3:]
    item = store.pending_collections.pop(token, None)
    if item is None:
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return
    owner_id, title, tracks = item
    if cq.from_user.id != owner_id:
        store.pending_collections[token] = item
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return
    await cq.answer()
    await cq.message.delete()
    await queue.process_collection(cq.bot, cq.message.chat.id, owner_id, title, tracks, t)


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
        await cq.answer("⏹")
    else:
        await cq.answer()
