"""Social media video link handler.

Detects links to Instagram, TikTok, YouTube/Shorts, Facebook, X/Twitter,
Pinterest and Vimeo in any incoming text message. Downloads the video, sends
it to the chat, then attaches a 🎵 Find Music button that triggers Shazam
recognition on the video's audio track.

Routing note: this router must be registered BEFORE search.router so that
social media URLs are not treated as plain-text search queries.
"""

import html
import logging
import tempfile

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot import keyboards, store
from bot.admin import settings_store
from bot.i18n import Texts
from bot.services import media, recognizer, search_engine, video_dl

log = logging.getLogger(__name__)
router = Router(name="video")

_PLATFORM_ICONS: dict[str, str] = {
    "Instagram": "📸",
    "TikTok":    "🎵",
    "YouTube":   "▶️",
    "Facebook":  "🎬",
    "X/Twitter": "🐦",
    "Pinterest": "📌",
    "Vimeo":     "🎥",
}


def _has_video_url(text: str) -> bool:
    pair = video_dl.extract_video_url(text)
    if not pair:
        return False
    # YouTube URLs are handled by youtube.router (audio extraction)
    return pair[1] != "YouTube"


@router.message(F.text.func(_has_video_url))
async def handle_video_link(message: Message, t: Texts, bot: Bot) -> None:
    pair = video_dl.extract_video_url(message.text or "")
    if not pair:
        return
    if not settings_store.feature_enabled("video"):
        await message.answer("🎬 Video download is temporarily disabled.")
        return

    url, platform = pair
    icon = _PLATFORM_ICONS.get(platform, "🎬")
    status = await message.answer(t.VIDEO_DOWNLOADING.format(platform=f"{icon} {platform}"))

    try:
        with tempfile.TemporaryDirectory(prefix="vidl_") as tmpdir:
            info = await media.backend().download_video(url, platform, tmpdir)

            token = store.stash_video(url)
            esc = html.escape

            caption_lines = [f"{icon} <b>{esc(platform)}</b>"]
            if info.title:
                title_short = info.title[:80] + ("…" if len(info.title) > 80 else "")
                caption_lines.append(f"🎬 {esc(title_short)}")
            if info.duration:
                mins, secs = divmod(info.duration, 60)
                caption_lines.append(f"⏱ {mins}:{secs:02d}")

            caption = "\n".join(caption_lines)

            await status.delete()
            await bot.send_video(
                message.chat.id,
                video=FSInputFile(info.video_path),
                caption=caption,
                duration=info.duration or None,
                reply_markup=keyboards.video_result_kb(token, t),
                supports_streaming=True,
            )

    except FileNotFoundError:
        log.warning("Video not found after download: %s", url)
        await status.edit_text(t.VIDEO_PRIVATE)
    except ValueError as exc:
        msg = str(exc).lower()
        if "large" in msg:
            await status.edit_text(t.VIDEO_TOO_LARGE)
        elif any(w in msg for w in ("private", "unavailable", "not available", "login")):
            await status.edit_text(t.VIDEO_PRIVATE)
        else:
            log.warning("Video download rejected (%s): %s", platform, exc)
            await status.edit_text(t.VIDEO_ERROR)
    except Exception:
        log.exception("Video download failed (%s): %s", platform, url)
        await status.edit_text(t.VIDEO_ERROR)


# ─── 🎵 Find Music callback ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vm:"))
async def cb_find_music(cq: CallbackQuery, t: Texts) -> None:
    token = cq.data[3:]
    url = store.pending_videos.get(token)
    if not url:
        await cq.answer(t.ERR_EXPIRED, show_alert=True)
        return

    await cq.answer()
    status = await cq.message.answer(t.FINDING_MUSIC)

    try:
        with tempfile.TemporaryDirectory(prefix="vidrecog_") as tmpdir:
            audio_path = await media.backend().extract_audio(url, tmpdir)
            result = await recognizer.recognize(audio_path)
    except Exception:
        log.exception("Find-music pipeline failed: %s", url)
        await status.edit_text(t.ERR_GENERIC)
        return

    if not result:
        await status.edit_text(t.RECOGNIZE_NOT_FOUND)
        return

    # Search for a downloadable version of the identified track
    query = f"{result['artist']} {result['title']}"
    try:
        tracks = await search_engine.search(query, limit=5)
    except Exception:
        log.exception("Post-recognition search failed: %s", query)
        tracks = []

    track = tracks[0] if tracks else None
    if track:
        store.remember([track])

    # Build recognition card (same layout as recognize.py)
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
    markup = keyboards.recognize_result_kb(track, t) if track else None

    await status.delete()

    cover = result.get("cover")
    if cover:
        try:
            await cq.message.answer_photo(photo=cover, caption=caption, reply_markup=markup)
            return
        except Exception:
            log.debug("Cover photo send failed, falling back to text")

    await cq.message.answer(caption, reply_markup=markup)
