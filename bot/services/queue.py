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

from bot import keyboards, store, texts
from bot.db import repo
from bot.services import downloader
from bot.services.downloader import Downloaded, TooLarge, TrackNotFound
from bot.services.spotify import Track, spotify

log = logging.getLogger(__name__)

PARALLEL_DOWNLOADS = 3


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


async def _retrying(fn):
    """Telegram flood-limitiga tushganda kutib qayta yuboradi."""
    for _ in range(3):
        try:
            return await fn()
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
    return await fn()


async def _send_cached(bot: Bot, chat_id: int, file_id: str, track: Track) -> Message:
    return await _retrying(
        lambda: bot.send_audio(
            chat_id=chat_id,
            audio=file_id,
            reply_markup=keyboards.track_buttons(track),
        )
    )


async def _send_file(bot: Bot, chat_id: int, res: Downloaded, track: Track) -> Message:
    thumb = FSInputFile(res.thumb_path) if res.thumb_path else None
    return await _retrying(
        lambda: bot.send_audio(
            chat_id=chat_id,
            audio=FSInputFile(res.mp3_path),
            title=track.title,
            performer=track.artists,
            duration=track.duration or None,
            thumbnail=thumb,
            reply_markup=keyboards.track_buttons(track),
        )
    )


async def _safe_edit(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except (TelegramBadRequest, TelegramRetryAfter):
        pass


async def _resolve_track(track_id: str) -> Track | None:
    """Trek metadatasini topadi. "yt:" prefiksli treklar YouTube qidiruvidan kelgan."""
    if not track_id.startswith("yt:"):
        return await spotify.track(track_id)
    track = store.get_yt(track_id)
    if track is not None:
        return track
    # Bot qayta ishga tushgan bo'lsa — keshdagi nom/ijrochidan tiklaymiz
    row = await repo.cache_any_row(track_id)
    if row is None:
        return None
    return Track(
        id=track_id, title=row["title"] or "", artists=row["artist"] or "",
        artist_id="", album="", album_id="", duration=0,
        cover_url="", thumb_url="", year="", track_no=0,
        video_id=track_id[3:],
    )


async def process_single(bot: Bot, chat_id: int, user_id: int, track_id: str) -> None:
    """Bitta trekni topib yuboradi (kesh → yuklab olish)."""
    status = await bot.send_message(chat_id, texts.SEARCHING)
    try:
        track = await _resolve_track(track_id)
        if track is None:
            await _safe_edit(status, texts.ERR_EXPIRED)
            return
        bitrate = await repo.get_quality(user_id)

        file_id = await repo.cache_get(track.id, bitrate)
        if file_id:
            await _send_cached(bot, chat_id, file_id, track)
            await repo.incr("cache_hits")
        else:
            await _safe_edit(status, texts.DOWNLOADING)
            with tempfile.TemporaryDirectory(prefix="spdl_") as tmp:
                res = await downloader.download(track, bitrate, tmp)
                msg = await _send_file(bot, chat_id, res, track)
                if msg.audio:
                    await repo.cache_put(
                        track.id, bitrate, msg.audio.file_id, track.title, track.artists
                    )
            await repo.incr("downloads")

        await repo.add_history(user_id, track.id, track.title, track.artists)
        await status.delete()
    except TrackNotFound:
        await _safe_edit(status, texts.ERR_NOT_FOUND.format(name=html.escape(track.full_name)))
    except TooLarge:
        await _safe_edit(status, texts.ERR_TOO_LARGE.format(name=html.escape(track.full_name)))
    except Exception:
        log.exception("Trek yuborishda xato: %s", track_id)
        await _safe_edit(status, texts.ERR_GENERIC)


async def process_collection(
    bot: Bot, chat_id: int, user_id: int, title: str, tracks: list[Track]
) -> None:
    """Albom/playlist/liked to'plamini parallel yuklab, tartib bilan yuboradi."""
    if user_id in manager.active:
        await bot.send_message(chat_id, texts.ERR_BUSY)
        return

    job = Job()
    manager.active[user_id] = job
    bitrate = await repo.get_quality(user_id)
    total = len(tracks)
    title = html.escape(title)

    status = await bot.send_message(
        chat_id,
        texts.PROGRESS.format(
            icon="⏳", title=title, bar=texts.progress_bar(0, total),
            done=0, total=total, sent=0, failed=0,
        ),
        reply_markup=keyboards.cancel_button(user_id),
    )

    sem = asyncio.Semaphore(PARALLEL_DOWNLOADS)

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
                res = await downloader.download(track, bitrate, tmp.name)
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

    tasks = [asyncio.create_task(prepare(t)) for t in tracks]
    sent = failed = consumed = 0
    failed_names: list[str] = []
    last_edit = 0.0

    try:
        for i, (track, task) in enumerate(zip(tracks, tasks), start=1):
            if job.cancelled:
                break
            kind, payload = await task
            consumed = i

            if kind == "cached":
                try:
                    await _send_cached(bot, chat_id, payload, track)
                    await repo.incr("cache_hits")
                    await repo.add_history(user_id, track.id, track.title, track.artists)
                    sent += 1
                except Exception:
                    log.exception("Keshdan yuborishda xato: %s", track.full_name)
                    failed += 1
                    failed_names.append(html.escape(track.full_name))
            elif kind == "file":
                tmp, res = payload
                try:
                    msg = await _send_file(bot, chat_id, res, track)
                    if msg.audio:
                        await repo.cache_put(
                            track.id, bitrate, msg.audio.file_id,
                            track.title, track.artists,
                        )
                    await repo.incr("downloads")
                    await repo.add_history(user_id, track.id, track.title, track.artists)
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
            if now - last_edit > 2.5 or i == total:
                await _safe_edit(
                    status,
                    texts.PROGRESS.format(
                        icon="⬇️", title=title, bar=texts.progress_bar(i, total),
                        done=i, total=total, sent=sent, failed=failed,
                    ),
                    reply_markup=keyboards.cancel_button(user_id),
                )
                last_edit = now
            await asyncio.sleep(0.3)
    finally:
        # Iste'mol qilinmagan tasklarni tozalaymiz (temp papkalar oqib ketmasin)
        for task in tasks[consumed:]:
            if not task.done():
                task.cancel()
            else:
                try:
                    kind, payload = task.result()
                    if kind == "file":
                        payload[0].cleanup()
                except Exception:
                    pass
        manager.active.pop(user_id, None)

    if job.cancelled:
        await _safe_edit(status, texts.COLLECTION_CANCELLED.format(sent=sent, total=total))
        return

    text = texts.COLLECTION_DONE.format(title=title, sent=sent, total=total)
    if failed_names:
        shown = ", ".join(failed_names[:5])
        if len(failed_names) > 5:
            shown += f" va yana {len(failed_names) - 5} ta"
        text += texts.COLLECTION_FAILED_LIST.format(names=shown)
    await _safe_edit(status, text)
