"""Music Recognition — identify songs from any media the user sends.

Accepted input: audio, voice message, video, video note (round video).
Workflow:
  1. Download media to temp dir.
  2. Extract 30-second audio clip (FFmpeg, skips intro).
  3. Query Shazam via audio fingerprinting.
  4. Search our engine for a downloadable version of the identified track.
  5. Reply with a rich photo card + action keyboard.
"""

import html
import logging
import os
import tempfile

from aiogram import Bot, F, Router
from aiogram.enums import ContentType
from aiogram.types import Message

from bot import keyboards, store
from bot.admin import repo as admin_repo
from bot.admin import settings_store
from bot.i18n import Texts
from bot.services import recognizer, search_engine, tg_limits

log = logging.getLogger(__name__)
router = Router(name="recognize")

_SUPPORTED_TYPES = {
    ContentType.AUDIO,
    ContentType.VOICE,
    ContentType.VIDEO,
    ContentType.VIDEO_NOTE,
}



def _file_obj(message: Message):
    return message.audio or message.voice or message.video or message.video_note


def _ext(message: Message) -> str:
    if message.audio:
        fn = getattr(message.audio, "file_name", "") or ""
        suffix = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
        return suffix if suffix in ("mp3", "m4a", "ogg", "flac", "wav", "aac", "opus") else "mp3"
    if message.voice:
        return "ogg"
    return "mp4"  # video / video_note


@router.message(F.content_type.in_(_SUPPORTED_TYPES))
async def handle_media(message: Message, t: Texts, bot: Bot) -> None:
    if not settings_store.feature_enabled("recognize"):
        await message.answer("🎧 Music recognition is temporarily disabled.")
        return

    file_obj = _file_obj(message)
    if file_obj is None:
        return

    # Silently skip files that exceed the bot download limit
    size = getattr(file_obj, "file_size", None) or 0
    if size and size > tg_limits.max_download_bytes():
        await message.answer(t.RECOGNIZE_TOO_LARGE)
        return

    status = await message.answer(t.RECOGNIZING)

    try:
        with tempfile.TemporaryDirectory(prefix="recog_") as tmpdir:
            media_path = os.path.join(tmpdir, f"media.{_ext(message)}")
            await bot.download(file_obj, destination=media_path)
            result = await recognizer.recognize(media_path)
    except Exception:
        log.exception("Recognition pipeline error")
        await status.edit_text(t.ERR_GENERIC)
        return

    if not result:
        try:
            await admin_repo.add_failed("recognize", "unidentified media")
        except Exception:
            pass
        await status.edit_text(t.RECOGNIZE_NOT_FOUND)
        return

    try:
        await admin_repo.bump_song(
            f"{(result['artist'] or '').strip().lower()} — {(result['title'] or '').strip().lower()}"[:200],
            result.get("title") or "", result.get("artist") or "", "recognitions",
        )
    except Exception:
        pass

    # Find a downloadable version via our multi-source search engine
    query = f"{result['artist']} {result['title']}"
    try:
        tracks = await search_engine.search(query, limit=5)
    except Exception:
        log.exception("Post-recognition search failed: %s", query)
        tracks = []

    track = tracks[0] if tracks else None
    if track:
        store.remember([track])

    # Build caption
    esc = html.escape
    lines = [t.RECOGNIZE_HEADER]
    lines.append(f"🎵 <b>{esc(result['title'])}</b>")
    lines.append(f"👤 {esc(result['artist'])}")

    meta_parts: list[str] = []
    if result.get("album"):
        meta_parts.append(f"💿 {esc(result['album'])}")
    if result.get("year"):
        meta_parts.append(f"📅 {result['year']}")
    if result.get("genre"):
        meta_parts.append(f"🎼 {esc(result['genre'])}")
    if meta_parts:
        lines.append(" · ".join(meta_parts))

    if track and track.duration:
        mins, secs = divmod(track.duration, 60)
        lines.append(f"⏱ {mins}:{secs:02d}")

    caption = "\n".join(lines)
    reply_markup = keyboards.recognize_result_kb(track, t) if track else None

    await status.delete()

    cover = result.get("cover")
    if cover:
        try:
            await message.answer_photo(
                photo=cover,
                caption=caption,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            log.debug("Cover photo send failed, falling back to text")

    await message.answer(caption, reply_markup=reply_markup)
