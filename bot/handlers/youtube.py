"""YouTube link handler — extracts audio from YouTube videos and playlists.

When a user sends a YouTube URL the bot downloads the audio track (not the
video) and delivers it with the full post-download UX (Share, Favorites,
Similar Songs, Audio Effects, Metadata Editor).

Routing: this router must be registered BEFORE video.router so that YouTube
URLs are handled as audio downloads rather than video downloads.
"""

import html
import logging
import tempfile

from aiogram import Bot, F, Router
from aiogram.types import FSInputFile, Message

from bot import keyboards, store
from bot.db import repo
from bot.i18n import Texts, track_caption
from bot.services import downloader, video_dl
from bot.services.downloader import TooLarge, TrackNotFound
from bot.services.spotify import Track

log = logging.getLogger(__name__)
router = Router(name="youtube")


def _is_youtube_url(text: str) -> bool:
    return video_dl.is_youtube_url(text)


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


def _minimal_track(video_id: str) -> Track:
    thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    mqthumb = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
    return Track(
        id=f"yt:{video_id}",
        title="",
        artists="",
        artist_id="",
        album="",
        album_id="",
        duration=0,
        cover_url=thumb,
        thumb_url=mqthumb,
        year="",
        track_no=0,
        video_id=video_id,
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

    status = await message.answer(t.YT_PROCESSING)

    # Try to get metadata first (non-blocking, best-effort)
    track: Track | None = None
    try:
        meta = await video_dl.extract_yt_meta(video_id)
        track = _yt_track(meta)
    except Exception:
        log.debug("YouTube metadata extraction failed for %s, will get info during download", video_id)

    if track is None:
        track = _minimal_track(video_id)

    store.remember([track])

    # Show info card if we have metadata
    if track.title:
        esc = html.escape
        info_text = (
            f"▶️ <b>YouTube</b>\n"
            f"🎵 <b>{esc(track.title)}</b>\n"
            f"👤 {esc(track.artists)}"
        )
        if track.duration:
            mins, secs = divmod(track.duration, 60)
            info_text += f"\n⏱ {mins}:{secs:02d}"
        info_text += f"\n\n{t.DOWNLOADING}"
        try:
            await status.edit_text(info_text)
        except Exception:
            pass
    else:
        try:
            await status.edit_text(t.DOWNLOADING)
        except Exception:
            pass

    user_id = message.from_user.id
    bitrate = await repo.get_quality(user_id)

    # Check cache
    file_id = await repo.cache_get(track.id, bitrate)
    if file_id:
        is_fav = await repo.is_favorite(user_id, track.id)
        await bot.send_audio(
            chat_id=message.chat.id,
            audio=file_id,
            caption=track_caption(track),
            reply_markup=keyboards.post_download_kb(track, t, is_fav),
        )
        await repo.incr("cache_hits")
        await status.delete()
        return

    # Download audio
    try:
        with tempfile.TemporaryDirectory(prefix="ytdl_") as tmpdir:
            res = await downloader.download(track, bitrate, tmpdir)

            # If metadata was missing, try to read title/artist from the downloaded MP3 tags
            if not track.title:
                track = _enrich_from_file(track, res.mp3_path)
                store.remember([track])

            thumb = FSInputFile(res.thumb_path) if res.thumb_path else None
            is_fav = await repo.is_favorite(user_id, track.id)

            msg = await bot.send_audio(
                chat_id=message.chat.id,
                audio=FSInputFile(res.mp3_path),
                title=track.title or None,
                performer=track.artists or None,
                duration=track.duration or None,
                thumbnail=thumb,
                caption=track_caption(track),
                reply_markup=keyboards.post_download_kb(track, t, is_fav),
            )

            if msg.audio:
                await repo.cache_put(
                    track.id, bitrate, msg.audio.file_id,
                    track.title, track.artists,
                )

        await repo.incr("downloads")
        await status.delete()

    except TrackNotFound:
        await status.edit_text(t.YT_UNAVAILABLE)
    except TooLarge:
        name = html.escape(track.full_name) if track.title else "YouTube video"
        await status.edit_text(t.ERR_TOO_LARGE.format(name=name))
    except Exception:
        log.exception("YouTube audio download failed: %s", video_id)
        await status.edit_text(t.YT_UNAVAILABLE)


def _enrich_from_file(track: Track, mp3_path: str) -> Track:
    """Try to read title/artist from MP3 ID3 tags written by yt-dlp."""
    try:
        from mutagen.id3 import ID3
        tags = ID3(mp3_path)
        title = str(tags.get("TIT2", "")) or ""
        artist = str(tags.get("TPE1", "")) or ""
        if title or artist:
            from dataclasses import replace
            return replace(track, title=title or track.title, artists=artist or track.artists)
    except Exception:
        pass
    return track


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
