"""Treklarni yuborish: kesh, parallel yuklab olish, progress va bekor qilish."""

import asyncio
import html
import logging
import tempfile
import time
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import FSInputFile, Message

from bot import keyboards, store
from bot.admin import repo as admin_repo
from bot.db import repo
from bot.i18n import Texts, progress_bar, track_caption
from bot.services import media
from bot.services.downloader import Downloaded, TooLarge, TrackNotFound
from bot.services.spotify import Track, spotify

log = logging.getLogger(__name__)

PARALLEL_PER_USER = 6


@dataclass
class Job:
    cancelled: bool = field(default=False)


class TaskManager:
    def __init__(self) -> None:
        self.active: dict[int, Job] = {}

    def cancel(self, user_id: int) -> bool:
        job = self.active.get(user_id)
        if job:
            job.cancelled = True
            return True
        return False


manager = TaskManager()


def _song_key(track: Track) -> str:
    return f"{(track.artists or '').strip().lower()} — {(track.title or '').strip().lower()}"[:200]


async def _record_download(track: Track) -> None:
    """Analitika uchun: kunlik hisoblagich + qo'shiq statistikasi (hech qachon fail bermaydi)."""
    try:
        await admin_repo.incr_daily("downloads")
        await admin_repo.bump_song(
            _song_key(track), track.title or "", track.artists or "", "downloads"
        )
    except Exception:
        log.debug("download stat yozib bo'lmadi", exc_info=True)


async def _retrying(fn):
    for attempt in range(4):
        try:
            return await fn()
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramBadRequest:
            raise
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))


async def _send_cached(
    bot: Bot, chat_id: int, user_id: int, file_id: str, track: Track, t: Texts,
    *, full_kb: bool = False,
) -> Message:
    is_fav = await repo.is_favorite(user_id, track.id)
    markup = (
        keyboards.post_download_kb(track, t, is_fav)
        if full_kb
        else keyboards.track_buttons(track, t, is_fav)
    )
    return await _retrying(
        lambda: bot.send_audio(
            chat_id=chat_id,
            audio=file_id,
            caption=track_caption(track),
            reply_markup=markup,
        )
    )


async def _send_file(
    bot: Bot, chat_id: int, user_id: int, res: Downloaded, track: Track, t: Texts,
    *, full_kb: bool = False,
) -> Message:
    thumb = FSInputFile(res.thumb_path) if res.thumb_path else None
    is_fav = await repo.is_favorite(user_id, track.id)
    markup = (
        keyboards.post_download_kb(track, t, is_fav)
        if full_kb
        else keyboards.track_buttons(track, t, is_fav)
    )
    return await _retrying(
        lambda: bot.send_audio(
            chat_id=chat_id,
            audio=FSInputFile(res.mp3_path),
            title=track.title,
            performer=track.artists,
            duration=track.duration or None,
            thumbnail=thumb,
            caption=track_caption(track),
            reply_markup=markup,
        )
    )


async def _safe_edit(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except (TelegramBadRequest, TelegramRetryAfter):
        pass


async def _resolve_track(track_id: str) -> Track | None:
    # 1) Qidiruv natijalari xotirada — tarmoqqa murojaatsiz.
    track = store.get(track_id)
    if track is not None:
        return track
    # 2) YouTube treki — keshdan/sevimlilardan title/artist tiklaymiz, video_id id'dan.
    if track_id.startswith("yt:"):
        row = await repo.any_meta_row(track_id)
        if row is None:
            return None
        return Track(
            id=track_id, title=row["title"] or "", artists=row["artist"] or "",
            artist_id="", album="", album_id="", duration=0,
            cover_url="", thumb_url="", year="", track_no=0,
            video_id=track_id[3:],
        )
    # 3) Sintetik provayder id'lari (iTunes/Deezer) xotirada yashaydi. Xotira bo'sh
    #    bo'lsa (bot qayta ishga tushgan) — nomi bo'yicha tiklaymiz: sevimlilar va
    #    kesh yozuvlarida title/artist bor, downloader esa YouTube'dan topib beradi.
    if track_id.startswith(("it:", "dz:")):
        row = await repo.any_meta_row(track_id)
        if row is None or not (row["title"] or row["artist"]):
            return None
        return Track(
            id=track_id, title=row["title"] or "", artists=row["artist"] or "",
            artist_id="", album="", album_id="", duration=0,
            cover_url="", thumb_url="", year="", track_no=0,
        )
    # 4) Haqiqiy Spotify trek id'si (havoladan) — rasmiy/embed orqali olamiz.
    return await spotify.track(track_id)


async def process_single(bot: Bot, chat_id: int, user_id: int, track_id: str, t: Texts) -> None:
    status = await bot.send_message(chat_id, t.SEARCHING)
    try:
        track = await _resolve_track(track_id)
        if track is None:
            await _safe_edit(status, t.ERR_EXPIRED)
            return
        bitrate = await repo.get_quality(user_id)

        file_id = await repo.cache_get(track.id, bitrate)
        if file_id:
            await _send_cached(bot, chat_id, user_id, file_id, track, t, full_kb=True)
            await repo.incr("cache_hits")
        else:
            await _safe_edit(status, t.DOWNLOADING)
            with tempfile.TemporaryDirectory(prefix="spdl_") as tmp:
                res = await media.backend().download_track(track, bitrate, tmp)
                msg = await _send_file(bot, chat_id, user_id, res, track, t, full_kb=True)
                if msg.audio:
                    await repo.cache_put(
                        track.id, bitrate, msg.audio.file_id, track.title, track.artists
                    )
            await repo.incr("downloads")

        await _record_download(track)
        await status.delete()
    except TrackNotFound:
        await _safe_edit(status, t.ERR_NOT_FOUND.format(name=html.escape(track.full_name)))
    except TooLarge:
        await _safe_edit(status, t.ERR_TOO_LARGE.format(name=html.escape(track.full_name)))
    except Exception:
        log.exception("Trek yuborishda xato: %s", track_id)
        await _safe_edit(status, t.ERR_GENERIC)


async def process_collection(
    bot: Bot, chat_id: int, user_id: int, title: str, tracks: list[Track], t: Texts
) -> None:
    if user_id in manager.active:
        await bot.send_message(chat_id, t.ERR_BUSY)
        return

    job = Job()
    manager.active[user_id] = job
    bitrate = await repo.get_quality(user_id)
    total = len(tracks)
    title = html.escape(title)

    status = await bot.send_message(
        chat_id,
        t.PROGRESS.format(
            title=title, bar=progress_bar(0, total),
            done=0, total=total, sent=0, failed=0,
        ),
        reply_markup=keyboards.cancel_button(user_id, t),
    )

    sem = asyncio.Semaphore(PARALLEL_PER_USER)

    async def prepare(track: Track):
        if job.cancelled:
            return "skip", None
        file_id = await repo.cache_get(track.id, bitrate)
        if file_id:
            return "cached", file_id
        async with sem:
            if job.cancelled:
                return "skip", None
            tmp = tempfile.TemporaryDirectory(prefix="spdl_")
            try:
                res = await media.backend().download_track(track, bitrate, tmp.name)
                return "file", (tmp, res)
            except TrackNotFound:
                tmp.cleanup()
                return "notfound", None
            except TooLarge:
                tmp.cleanup()
                return "toolarge", None
            except Exception:
                log.exception("Yuklab olishda xato: %s", track.full_name)
                tmp.cleanup()
                return "error", None

    # Disk backpressure: bir vaqtда faqat WINDOW ta yuklab olingan fayl diskда
    # turadi. Aks holda uzun playlistда tugagan MP3'lar (har biri ~49MB) navbat
    # bilan yuborilguncha to'planib 5GB diskни to'ldiradi. Har oyna ketma-ket
    # yuboriladi va tozalanadi, so'ng keyingisi yuklanadi.
    WINDOW = PARALLEL_PER_USER
    sent = failed = done = 0
    failed_names: list[str] = []
    last_edit = 0.0

    try:
        for start in range(0, total, WINDOW):
            if job.cancelled:
                break
            batch = tracks[start:start + WINDOW]
            prep = [asyncio.create_task(prepare(tr)) for tr in batch]
            try:
                for track, task in zip(batch, prep):
                    if job.cancelled:
                        break
                    kind, payload = await task
                    done += 1

                    if kind == "cached":
                        try:
                            await _send_cached(bot, chat_id, user_id, payload, track, t)
                            await repo.incr("cache_hits")
                            await _record_download(track)
                            sent += 1
                        except Exception:
                            log.exception("Keshdan yuborishda xato: %s", track.full_name)
                            failed += 1
                            failed_names.append(html.escape(track.full_name))
                    elif kind == "file":
                        tmp, res = payload
                        try:
                            msg = await _send_file(bot, chat_id, user_id, res, track, t)
                            if msg.audio:
                                await repo.cache_put(
                                    track.id, bitrate, msg.audio.file_id,
                                    track.title, track.artists,
                                )
                            await repo.incr("downloads")
                            await _record_download(track)
                            sent += 1
                        except Exception:
                            log.exception("Faylni yuborishda xato: %s", track.full_name)
                            failed += 1
                            failed_names.append(html.escape(track.full_name))
                        finally:
                            tmp.cleanup()
                    elif kind == "skip":
                        continue
                    else:
                        failed += 1
                        failed_names.append(html.escape(track.full_name))

                    now = time.monotonic()
                    if now - last_edit > 2.5 or done == total:
                        await _safe_edit(
                            status,
                            t.PROGRESS.format(
                                title=title, bar=progress_bar(done, total),
                                done=done, total=total, sent=sent, failed=failed,
                            ),
                            reply_markup=keyboards.cancel_button(user_id, t),
                        )
                        last_edit = now
                    await asyncio.sleep(0.05)
            finally:
                # Iste'mol qilinmagan tasklarni (cancel/break) tozalaymiz —
                # tugaganlarning temp papkasini o'chiramiz, qolganini bekor.
                for task in prep:
                    if not task.done():
                        task.cancel()
                    else:
                        try:
                            k, p = task.result()
                            if k == "file":
                                p[0].cleanup()
                        except Exception:
                            pass
    finally:
        manager.active.pop(user_id, None)

    if job.cancelled:
        await _safe_edit(status, t.COLLECTION_CANCELLED.format(sent=sent, total=total))
        return

    text = t.COLLECTION_DONE.format(title=title, sent=sent, total=total)
    if failed_names:
        shown = ", ".join(failed_names[:5])
        if len(failed_names) > 5:
            shown += f" +{len(failed_names) - 5}"
        text += t.COLLECTION_FAILED_LIST.format(names=shown)
    await _safe_edit(status, text)
