"""YouTube link handler — extracts audio from YouTube videos and playlists.

Standard videos show a thumbnail preview with a format picker (MP3 / M4A /
FLAC / OPUS) and download nothing until the user taps a format. Playlists
render as a track list.

Shorts are NOT handled here — they go to video.router and are delivered as a
video with a 🎵 Find Music button, like every other social platform.

Routing: this router is registered BEFORE video.router, so `_is_youtube_url`
must reject Shorts in the filter; returning early from the handler would swallow
the update instead of passing it on.
"""

import html
import logging
import tempfile

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot import keyboards, store
from bot.db import repo
from bot.i18n import Texts, track_caption
from bot.services import media, tg_limits, video_dl, ytdlp_common
from bot.services.spotify import Track

log = logging.getLogger(__name__)
router = Router(name="youtube")

# video_dl.YTError.reason → lokalizatsiya kaliti
_ERR_TEXT = {
    "private": "YT_ERR_PRIVATE",
    "deleted": "YT_ERR_DELETED",
    "geo": "YT_ERR_GEO",
    "live": "YT_ERR_LIVE",
    "age": "YT_ERR_AGE",
    "blocked": "YT_ERR_BLOCKED",
    "network": "YT_ERR_NETWORK",
    "generic": "YT_UNAVAILABLE",
}


# Yuklanayotgan preview xabarlari: (chat_id, message_id)
_inflight: set[tuple[int, int]] = set()


def _err_text(t: Texts, reason: str) -> str:
    return getattr(t, _ERR_TEXT.get(reason, "YT_UNAVAILABLE"))


def _log_yt_error(video_id: str, e: "video_dl.YTError") -> None:
    """Xato sababini yozadi. `blocked` — operator muammosi, shuning uchun baland ovozda.

    `blocked` deyarli har doim YOUTUBE_COOKIES eskirgani yoki yt-dlp yangilanishi
    kerakligini bildiradi: YouTube data-markaz IP'sini bot deb hisoblaydi.
    """
    if e.reason == "blocked":
        log.error(
            "YouTube ekstraktor bloklandi (%s): cookies=%s yt-dlp=%s :: %s",
            video_id, ytdlp_common.has_cookies(), _ytdlp_version(), e,
        )
    else:
        log.warning("YouTube metadata %s: reason=%s :: %s", video_id, e.reason, e)


def _ytdlp_version() -> str:
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:
        return "?"


def _hms(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"


def _is_youtube_url(text: str) -> bool:
    """Oddiy YouTube videolari va playlistlar — Shorts emas.

    Shorts video.router'da ijtimoiy tarmoq videosi sifatida qayta ishlanadi.
    Bu router avval ro'yxatdan o'tgani uchun Shorts'ni **filtrda** rad etish
    shart: handler ichida `return` qilsak, aiogram keyingi routerga o'tkazmaydi.

    `youtube.com/playlist?list=…` (video id'siz) `is_youtube_url`ga tushmaydi —
    shu sabab playlist id'si alohida tekshiriladi, aks holda faqat
    `watch?v=…&list=…` ko'rinishidagi havolalar playlist deb qayta ishlanardi.
    """
    if video_dl.is_yt_shorts(text):
        return False
    return video_dl.is_youtube_url(text) or bool(video_dl.extract_yt_playlist_id(text))


def _yt_track(meta: video_dl.YTVideoMeta) -> Track:
    thumb = f"https://i.ytimg.com/vi/{meta.video_id}/hqdefault.jpg"
    mqthumb = f"https://i.ytimg.com/vi/{meta.video_id}/mqdefault.jpg"
    return Track(
        id=f"yt:{meta.video_id}",
        title=meta.title,
        artists=meta.channel,
        artist_id="",
        album="",
        album_id="",
        duration=meta.duration,
        cover_url=thumb,
        thumb_url=mqthumb,
        year="",
        track_no=0,
        video_id=meta.video_id,
    )


# ─── Single video ────────────────────────────────────────────────────────────

@router.message(F.text.func(_is_youtube_url))
async def handle_youtube_link(message: Message, t: Texts, bot: Bot) -> None:
    text = message.text or ""

    playlist_id = video_dl.extract_yt_playlist_id(text)
    if playlist_id:
        await _handle_playlist(message, playlist_id, t, bot)
        return

    video_id = video_dl.extract_yt_video_id(text)
    if not video_id:
        return

    await _show_preview(message, video_id, t)


# ─── Preview + format tanlash (oddiy videolar) ───────────────────────────────

async def _show_preview(message: Message, video_id: str, t: Texts) -> None:
    status = await message.answer(t.YT_FETCHING)

    try:
        meta = await video_dl.get_yt_meta(video_id)
    except video_dl.YTError as e:
        # Sababni yozmasak "mavjud emas" xabari sabab-siz qoladi va diagnostika imkonsiz.
        _log_yt_error(video_id, e)
        await status.edit_text(_err_text(t, e.reason))
        return
    except Exception:
        log.exception("YouTube metadata failed: %s", video_id)
        await status.edit_text(t.YT_UNAVAILABLE)
        return

    esc = html.escape
    title = meta.title or video_id
    caption = t.YT_CHOOSE_FORMAT.format(
        title=esc(title[:200]),
        channel=esc(meta.channel or "YouTube"),
        duration=f" · ⏱ {_hms(meta.duration)}" if meta.duration else "",
    )
    kb = keyboards.yt_formats(video_id, meta.formats, t)

    await status.delete()
    try:
        await message.answer_photo(meta.thumbnail, caption=caption, reply_markup=kb)
    except Exception:
        # Muqova yuklanmadi (webp/404) — matnli preview ham yetarli.
        log.debug("YouTube thumbnail send failed: %s", video_id)
        await message.answer(caption, reply_markup=kb)


@router.callback_query(F.data.startswith("ytf:"))
async def cb_yt_format(cq: CallbackQuery, t: Texts, bot: Bot) -> None:
    _, fmt, video_id = cq.data.split(":", 2)
    if fmt not in video_dl.FMT_ORDER:
        await cq.answer()
        return

    # Ikki marta tez bosilsa Telegram klaviaturani o'chirishga ulgurmaydi —
    # ikkinchi bosishni shu yerda to'xtatamiz, aks holda ikki marta yuklanadi.
    key = (cq.message.chat.id, cq.message.message_id)
    if key in _inflight:
        await cq.answer()
        return
    _inflight.add(key)

    try:
        await _run_format_download(cq, t, bot, fmt, video_id)
    finally:
        _inflight.discard(key)


async def _run_format_download(
    cq: CallbackQuery, t: Texts, bot: Bot, fmt: str, video_id: str,
) -> None:
    await cq.answer()
    preview = cq.message
    # Tugmalarni olib tashlaymiz — ikkinchi bosish yangi yuklashni boshlamasin.
    try:
        await preview.edit_caption(
            caption=t.YT_PREPARING.format(fmt=fmt.upper()), reply_markup=None
        )
    except Exception:
        try:
            await preview.edit_text(t.YT_PREPARING.format(fmt=fmt.upper()))
        except Exception:
            pass

    user_id = cq.from_user.id
    chat_id = preview.chat.id

    try:
        meta = await video_dl.get_yt_meta(video_id)
    except video_dl.YTError as e:
        _log_yt_error(video_id, e)
        await _fail(preview, _err_text(t, e.reason))
        return
    except Exception:
        log.exception("YouTube metadata failed on format pick: %s", video_id)
        await _fail(preview, t.YT_UNAVAILABLE)
        return

    track = _yt_track(meta)
    store.remember([track])
    cache_key = f"yt-{fmt}"

    file_id = await repo.cache_get(track.id, cache_key)
    if file_id:
        await _send_ready(bot, chat_id, user_id, file_id, None, track, fmt, t)
        await repo.incr("cache_hits")
        await _delete(preview)
        return

    try:
        with tempfile.TemporaryDirectory(prefix="ytfmt_") as tmpdir:
            path = await media.backend().download_yt_audio(video_id, fmt, tmpdir)
            msg = await _send_ready(
                bot, chat_id, user_id, None, path, track, fmt, t
            )
            file_id = msg.audio.file_id if msg.audio else (
                msg.document.file_id if msg.document else None
            )
            if file_id:
                await repo.cache_put(
                    track.id, cache_key, file_id, track.title, track.artists
                )
        await repo.incr("downloads")
        await _delete(preview)
    except video_dl.YTTooLarge:
        await _offer_smaller(preview, video_id, fmt, meta.formats, t)
    except video_dl.YTError as e:
        _log_yt_error(video_id, e)
        await _fail(preview, _err_text(t, e.reason))
    except Exception:
        log.exception("YouTube %s download failed: %s", fmt, video_id)
        await _fail(preview, t.YT_UNAVAILABLE)


async def _offer_smaller(
    preview: Message, video_id: str, fmt: str, available: tuple[str, ...], t: Texts,
) -> None:
    """Fayl chegaradan oshdi — yiqilish o'rniga kichikroq formatlarni taklif qilamiz."""
    alts = video_dl.smaller_formats(fmt, available)
    if not alts:
        # OPUS ham sig'madi: bundan kichigi yo'q.
        await _fail(preview, t.ERR_TOO_LARGE.format(name=fmt.upper()))
        return
    text = t.YT_TOO_LARGE_ALT.format(
        fmt=fmt.upper(), limit=tg_limits.human_mb(tg_limits.max_upload_bytes())
    )
    kb = keyboards.yt_formats(video_id, alts, t)
    try:
        await preview.edit_caption(caption=text, reply_markup=kb)
    except Exception:
        try:
            await preview.edit_text(text, reply_markup=kb)
        except Exception:
            pass


async def _send_ready(
    bot: Bot, chat_id: int, user_id: int, file_id: str | None,
    path: str | None, track: Track, fmt: str, t: Texts,
) -> Message:
    """Tayyor audioni yuboradi: mp3/m4a → pleyer, flac/opus → hujjat."""
    audio = file_id or FSInputFile(path)  # type: ignore[arg-type]
    if fmt in video_dl.AUDIO_FORMATS:
        is_fav = await repo.is_favorite(user_id, track.id)
        return await bot.send_audio(
            chat_id=chat_id,
            audio=audio,
            title=track.title or None,
            performer=track.artists or None,
            duration=track.duration or None,
            caption=track_caption(track),
            reply_markup=keyboards.post_download_kb(track, t, is_fav),
        )
    # Telegram pleyeri faqat mp3/m4a ni tanidi — FLAC/OPUS hujjat sifatida ketadi,
    # shunda sifat va teglar buzilmaydi.
    return await bot.send_document(
        chat_id=chat_id, document=audio, caption=track_caption(track)
    )


async def _fail(preview: Message, text: str) -> None:
    try:
        await preview.edit_caption(caption=text, reply_markup=None)
    except Exception:
        try:
            await preview.edit_text(text)
        except Exception:
            pass


async def _delete(msg: Message) -> None:
    try:
        await msg.delete()
    except Exception:
        pass


# ─── Playlist ────────────────────────────────────────────────────────────────

async def _handle_playlist(
    message: Message, playlist_id: str, t: Texts, bot: Bot,
) -> None:
    status = await message.answer(t.YT_PLAYLIST_LOADING)

    try:
        pl_meta = await video_dl.extract_yt_playlist(playlist_id)
    except Exception:
        log.exception("YouTube playlist extraction failed: %s", playlist_id)
        await status.edit_text(t.YT_UNAVAILABLE)
        return

    if not pl_meta.entries:
        await status.edit_text(t.YT_PLAYLIST_EMPTY)
        return

    tracks = [_yt_track(e) for e in pl_meta.entries if e.video_id]
    if not tracks:
        await status.edit_text(t.YT_PLAYLIST_EMPTY)
        return

    store.remember(tracks)
    token = store.stash_search(pl_meta.title, tracks)

    esc = html.escape
    total = len(tracks)

    text = (
        f"▶️ <b>YouTube Playlist</b>\n"
        f"📁 <b>{esc(pl_meta.title)}</b>\n"
        f"🎵 {total} {'tracks' if total != 1 else 'track'}"
    )
    if pl_meta.channel:
        text += f"\n👤 {esc(pl_meta.channel)}"
    text += f"\n\n<i>{t.YT_PLAYLIST_HINT}</i>"

    await status.delete()
    await message.answer(
        text,
        reply_markup=keyboards.search_results(tracks, token, 0, t, 6),
    )
