"""Post-download interactive experience: Share, Similar Songs, Audio Effects, Metadata Editor."""

import html
import io
import logging
import os
import subprocess
import tempfile
from dataclasses import replace
from math import ceil

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineQuery,
    InlineQueryResultCachedAudio,
    Message,
)
from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1
from mutagen.id3._util import ID3NoHeaderError

from bot import keyboards, store
from bot.db import repo
from bot.i18n import Texts, track_caption
from bot.services import audio_effects, downloader, recommender
from bot.services.spotify import Track, spotify

log = logging.getLogger(__name__)
router = Router(name="post_download")


# ─── FSM states for metadata field editing ───────────────────────────────────

class MetaEdit(StatesGroup):
    text_input  = State()   # waiting for a text field value
    photo_input = State()   # waiting for cover art photo


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _resolve_track(track_id: str) -> Track | None:
    track = store.get(track_id)
    if track is not None:
        return track
    if track_id.startswith("yt:"):
        row = await repo.cache_any_row(track_id)
        if row is None:
            return None
        return Track(
            id=track_id, title=row["title"] or "", artists=row["artist"] or "",
            artist_id="", album="", album_id="", duration=0,
            cover_url="", thumb_url="", year="", track_no=0,
            video_id=track_id[3:],
        )
    if track_id.startswith(("it:", "dz:")):
        return None
    return await spotify.track(track_id)


async def _get_audio_path(bot: Bot, track: Track, bitrate: str, tmpdir: str) -> str | None:
    """
    Obtain a local MP3 path for the track.
    First tries Telegram Bot API download (fast, ≤20 MB).
    Falls back to full YouTube re-download.
    """
    file_id = await repo.cache_get(track.id, bitrate) or await repo.cache_get(
        track.id, "128" if bitrate == "320" else "320"
    )
    if file_id:
        try:
            file_info = await bot.get_file(file_id)
            if not file_info.file_size or file_info.file_size <= 20 * 1024 * 1024:
                buf = io.BytesIO()
                await bot.download_file(file_info.file_path, destination=buf)
                path = os.path.join(tmpdir, "original.mp3")
                with open(path, "wb") as f:
                    f.write(buf.getvalue())
                return path
        except Exception:
            log.debug("Bot API download failed for %s, falling back to YT", track.id)

    try:
        res = await downloader.download(track, bitrate, tmpdir)
        return res.mp3_path
    except Exception:
        log.exception("YT re-download failed: %s", track.id)
        return None


def _patch_tag(path: str, field: str, value: str) -> None:
    """Apply a single metadata field update to an MP3 file."""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    {
        "title":  lambda: tags.add(TIT2(encoding=3, text=value)),
        "artist": lambda: tags.add(TPE1(encoding=3, text=value)),
        "album":  lambda: tags.add(TALB(encoding=3, text=value)),
        "year":   lambda: tags.add(TDRC(encoding=3, text=value)),
        "genre":  lambda: tags.add(TCON(encoding=3, text=value)),
    }.get(field, lambda: None)()
    tags.save(path, v2_version=3)


def _patch_cover(path: str, cover_bytes: bytes) -> None:
    """Replace cover art (APIC) in an MP3 file."""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("APIC")
    tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes))
    tags.save(path, v2_version=3)


def _updated_track(track: Track, field: str, value: str) -> Track:
    mapping = {
        "title":  dict(title=value),
        "artist": dict(artists=value),
        "album":  dict(album=value),
        "year":   dict(year=value),
        "genre":  dict(genre=value),
    }
    return replace(track, **mapping.get(field, {}))


# ─── Noop (page-number buttons in search/playlist keyboards) ─────────────────

@router.callback_query(F.data.in_({"noop", "pl:nop"}))
async def cb_noop(cq: CallbackQuery) -> None:
    await cq.answer()


# ─── Inline query: Share ──────────────────────────────────────────────────────
# Requires inline mode enabled in BotFather (@<botname> → Bot Settings → Inline Mode).

@router.inline_query(F.query.startswith("tid:"))
async def inline_share(query: InlineQuery) -> None:
    track_id = query.query[4:].strip()
    file_id = (
        await repo.cache_get(track_id, "320") or
        await repo.cache_get(track_id, "128")
    )
    if not file_id:
        await query.answer([], cache_time=10, is_personal=True)
        return

    track = await _resolve_track(track_id)
    if track:
        caption = (
            f"🎵 {html.escape(track.title)}\n"
            f"👤 {html.escape(track.artists)}\n\n"
            "✨ Shared via @track_drop_bot"
        )
    else:
        caption = "✨ Shared via @track_drop_bot"

    result = InlineQueryResultCachedAudio(
        id=track_id[-63:],
        audio_file_id=file_id,
        caption=caption,
    )
    await query.answer([result], cache_time=300, is_personal=True)


# ─── Similar Songs ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sim:"))
async def cb_similar(cq: CallbackQuery, t: Texts) -> None:
    track_id = cq.data[4:]
    track = await _resolve_track(track_id)
    if not track:
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return

    await cq.answer(t.SIMILAR_SEARCHING)

    try:
        tracks = await recommender.get_similar(track)
    except Exception:
        log.exception("Similar search error for track %s", track_id)
        await cq.message.answer(t.SIMILAR_EMPTY)
        return

    if not tracks:
        await cq.message.answer(t.SIMILAR_EMPTY)
        return

    store.remember(tracks)
    label = track.title or track.artists
    token = store.stash_search(label, tracks)
    pages = ceil(len(tracks) / 6)
    await cq.message.answer(
        t.SIMILAR_TITLE.format(
            title=html.escape(label),
            page=1, pages=pages,
        ),
        reply_markup=keyboards.search_results(tracks, token, 0, t, 6),
    )


# ─── Audio Effects: show menu ─────────────────────────────────────────────────

@router.callback_query(
    F.data.startswith("ea:") &
    ~F.data.startswith("ea:apply:") &
    ~F.data.startswith("ea:back:")
)
async def cb_effects_menu(cq: CallbackQuery, t: Texts) -> None:
    track_id = cq.data[3:]
    await cq.answer()
    try:
        await cq.message.edit_reply_markup(
            reply_markup=keyboards.audio_effects_kb(track_id, t)
        )
    except TelegramBadRequest:
        pass


# ─── Audio Effects: apply ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ea:apply:"))
async def cb_apply_effect(cq: CallbackQuery, t: Texts, bot: Bot) -> None:
    # "ea:apply:{effect}:{track_id}" — split at most 3 times to preserve track_id colons
    parts = cq.data.split(":", 3)
    effect = parts[2]
    track_id = parts[3]

    if effect not in audio_effects.EFFECTS:
        await cq.answer(t.EFFECTS_ERROR, show_alert=True)
        return

    effect_label = audio_effects.EFFECTS[effect]
    await cq.answer()

    status = await cq.message.answer(t.EFFECTS_PROCESSING.format(effect=effect_label))

    try:
        track = await _resolve_track(track_id)
        if not track:
            await status.edit_text(t.ERR_EXPIRED)
            return

        bitrate = await repo.get_quality(cq.from_user.id)

        with tempfile.TemporaryDirectory(prefix="spdl_fx_") as tmpdir:
            original = await _get_audio_path(bot, track, bitrate, tmpdir)
            if not original:
                await status.edit_text(t.EFFECTS_ERROR)
                return

            processed = os.path.join(tmpdir, f"fx_{effect}.mp3")
            await audio_effects.apply_effect(original, processed, effect)

            if os.path.getsize(processed) > 50 * 1024 * 1024:
                await status.edit_text(t.ERR_TOO_LARGE.format(name=html.escape(track.full_name)))
                return

            # Thumbnail: try to reuse from the original
            thumb_input = None
            if track.thumb_url:
                cover_bytes = await downloader._fetch_cover(track.thumb_url)
                if cover_bytes:
                    thumb_path = os.path.join(tmpdir, "thumb.jpg")
                    with open(thumb_path, "wb") as f:
                        f.write(cover_bytes)
                    thumb_input = FSInputFile(thumb_path)

            is_fav = await repo.is_favorite(cq.from_user.id, track_id)
            caption = f"🎚 <b>{html.escape(effect_label)}</b>\n" + track_caption(track)

            await bot.send_audio(
                cq.message.chat.id,
                audio=FSInputFile(processed),
                title=f"{track.title} ({effect_label})",
                performer=track.artists,
                duration=track.duration or None,
                thumbnail=thumb_input,
                caption=caption,
                reply_markup=keyboards.post_download_kb(track, t, is_fav),
            )

        await status.delete()

    except subprocess.CalledProcessError:
        log.exception("FFmpeg error: effect=%s track=%s", effect, track_id)
        await status.edit_text(t.EFFECTS_ERROR)
    except Exception:
        log.exception("Effect apply error: effect=%s track=%s", effect, track_id)
        await status.edit_text(t.EFFECTS_ERROR)


# ─── Audio Effects: back ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ea:back:"))
async def cb_effects_back(cq: CallbackQuery, t: Texts) -> None:
    track_id = cq.data[8:]
    track = await _resolve_track(track_id)
    is_fav = await repo.is_favorite(cq.from_user.id, track_id)
    await cq.answer()
    try:
        markup = keyboards.post_download_kb(track, t, is_fav) if track else None
        await cq.message.edit_reply_markup(reply_markup=markup)
    except TelegramBadRequest:
        pass


# ─── Metadata Editor: show menu ──────────────────────────────────────────────

@router.callback_query(
    F.data.startswith("em:") &
    ~F.data.startswith("em:f:") &
    ~F.data.startswith("em:back:") &
    ~F.data.startswith("em:cancel:")
)
async def cb_meta_menu(cq: CallbackQuery, t: Texts) -> None:
    track_id = cq.data[3:]
    await cq.answer()
    try:
        await cq.message.edit_reply_markup(
            reply_markup=keyboards.metadata_editor_kb(track_id, t)
        )
    except TelegramBadRequest:
        pass


# ─── Metadata Editor: select field ───────────────────────────────────────────

@router.callback_query(F.data.startswith("em:f:"))
async def cb_meta_field(cq: CallbackQuery, t: Texts, state: FSMContext) -> None:
    # "em:f:{field}:{track_id}" — split at most 3 times
    parts = cq.data.split(":", 3)
    field = parts[2]
    track_id = parts[3]

    prompts = {
        "title":  t.META_ASK_TITLE,
        "artist": t.META_ASK_ARTIST,
        "album":  t.META_ASK_ALBUM,
        "year":   t.META_ASK_YEAR,
        "genre":  t.META_ASK_GENRE,
        "cover":  t.META_ASK_COVER,
    }
    prompt_text = prompts.get(field, "Enter value:")
    await cq.answer()

    prompt_msg = await cq.message.answer(
        prompt_text,
        reply_markup=keyboards.cancel_meta_kb(track_id, t),
    )

    if field == "cover":
        await state.set_state(MetaEdit.photo_input)
    else:
        await state.set_state(MetaEdit.text_input)

    await state.update_data(
        track_id=track_id,
        field=field,
        prompt_msg_id=prompt_msg.message_id,
        chat_id=cq.message.chat.id,
    )


# ─── Metadata Editor: back ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("em:back:"))
async def cb_meta_back(cq: CallbackQuery, t: Texts, state: FSMContext) -> None:
    track_id = cq.data[8:]
    await state.clear()
    track = await _resolve_track(track_id)
    is_fav = await repo.is_favorite(cq.from_user.id, track_id)
    await cq.answer()
    try:
        markup = keyboards.post_download_kb(track, t, is_fav) if track else None
        await cq.message.edit_reply_markup(reply_markup=markup)
    except TelegramBadRequest:
        pass


# ─── Metadata Editor: cancel field input ─────────────────────────────────────

@router.callback_query(F.data.startswith("em:cancel:"))
async def cb_meta_cancel(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.answer()
    try:
        await cq.message.delete()
    except TelegramBadRequest:
        pass


# ─── Metadata Editor: receive text value ─────────────────────────────────────

@router.message(MetaEdit.text_input, F.text)
async def meta_text_received(message: Message, t: Texts, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    track_id = data["track_id"]
    field = data["field"]
    new_value = message.text.strip()

    await state.clear()

    try:
        await bot.delete_message(message.chat.id, data["prompt_msg_id"])
    except Exception:
        pass

    status = await message.answer(t.META_PROCESSING)

    try:
        track = await _resolve_track(track_id)
        if not track:
            await status.edit_text(t.META_ERROR)
            return

        bitrate = await repo.get_quality(message.from_user.id)

        with tempfile.TemporaryDirectory(prefix="spdl_meta_") as tmpdir:
            audio_path = await _get_audio_path(bot, track, bitrate, tmpdir)
            if not audio_path:
                await status.edit_text(t.META_ERROR)
                return

            _patch_tag(audio_path, field, new_value)

            updated = _updated_track(track, field, new_value)
            is_fav = await repo.is_favorite(message.from_user.id, track_id)

            # Try to keep original thumbnail
            thumb_input = None
            if track.thumb_url:
                cover_bytes = await downloader._fetch_cover(track.thumb_url)
                if cover_bytes:
                    thumb_path = os.path.join(tmpdir, "thumb.jpg")
                    with open(thumb_path, "wb") as f:
                        f.write(cover_bytes)
                    thumb_input = FSInputFile(thumb_path)

            await bot.send_audio(
                message.chat.id,
                audio=FSInputFile(audio_path),
                title=updated.title,
                performer=updated.artists,
                duration=updated.duration or None,
                thumbnail=thumb_input,
                caption=track_caption(updated),
                reply_markup=keyboards.post_download_kb(updated, t, is_fav),
            )

        await status.delete()
        await repo.add_history(message.from_user.id, track_id, updated.title, updated.artists)

    except Exception:
        log.exception("Metadata text update error: %s", track_id)
        await status.edit_text(t.META_ERROR)


# ─── Metadata Editor: receive cover photo ────────────────────────────────────

@router.message(MetaEdit.photo_input, F.photo)
async def meta_photo_received(message: Message, t: Texts, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    track_id = data["track_id"]

    await state.clear()

    try:
        await bot.delete_message(message.chat.id, data["prompt_msg_id"])
    except Exception:
        pass

    status = await message.answer(t.META_PROCESSING)

    try:
        track = await _resolve_track(track_id)
        if not track:
            await status.edit_text(t.META_ERROR)
            return

        # Download the user-supplied photo (largest size)
        photo = message.photo[-1]
        photo_buf = io.BytesIO()
        await bot.download(photo, destination=photo_buf)
        cover_bytes = photo_buf.getvalue()

        bitrate = await repo.get_quality(message.from_user.id)

        with tempfile.TemporaryDirectory(prefix="spdl_meta_") as tmpdir:
            audio_path = await _get_audio_path(bot, track, bitrate, tmpdir)
            if not audio_path:
                await status.edit_text(t.META_ERROR)
                return

            _patch_cover(audio_path, cover_bytes)

            thumb_path = os.path.join(tmpdir, "thumb.jpg")
            with open(thumb_path, "wb") as f:
                f.write(cover_bytes)

            is_fav = await repo.is_favorite(message.from_user.id, track_id)

            await bot.send_audio(
                message.chat.id,
                audio=FSInputFile(audio_path),
                title=track.title,
                performer=track.artists,
                duration=track.duration or None,
                thumbnail=FSInputFile(thumb_path),
                caption=track_caption(track),
                reply_markup=keyboards.post_download_kb(track, t, is_fav),
            )

        await status.delete()
        await repo.add_history(message.from_user.id, track_id, track.title, track.artists)

    except Exception:
        log.exception("Metadata cover update error: %s", track_id)
        await status.edit_text(t.META_ERROR)
