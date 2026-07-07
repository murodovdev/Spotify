"""YouTube'dan audio yuklab olish, MP3 ga aylantirish va teglash."""

import asyncio
import glob
import logging
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache

import aiohttp
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TRCK
from mutagen.id3._util import ID3NoHeaderError
from yt_dlp import YoutubeDL

from bot.services import matcher, ytdlp_common
from bot.services.spotify import Track, spotify

log = logging.getLogger(__name__)

MAX_SIZE = 49 * 1024 * 1024
LONG_TRACK_SECONDS = 1200

_MAX_CONCURRENT = int(os.getenv("MAX_DOWNLOADS", "4"))
_download_sem = asyncio.Semaphore(_MAX_CONCURRENT)
_executor = ThreadPoolExecutor(max_workers=_MAX_CONCURRENT, thread_name_prefix="dl")


class TrackNotFound(Exception):
    pass


class TooLarge(Exception):
    pass


@dataclass(slots=True)
class Downloaded:
    mp3_path: str
    thumb_path: str | None


@lru_cache(maxsize=1)
def _ffmpeg_location() -> str | None:
    if shutil.which("ffmpeg"):
        return None
    winget_bin = (
        r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.1.2-full_build\bin"
    )
    if os.path.isfile(os.path.join(winget_bin, "ffmpeg.exe")):
        return winget_bin
    return None


def _ydl_download(video_id: str, tmpdir: str, bitrate: str) -> str:
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 3,
        "socket_timeout": 20,
    }
    # Cookie + chidamli player_client — data-markaz IP'lardagi "bot" tekshiruvi
    # va yosh-cheklovini chetlab o'tish uchun (bot/services/ytdlp_common.py).
    ytdlp_common.apply(opts)
    ffmpeg_loc = _ffmpeg_location()
    if ffmpeg_loc:
        opts["ffmpeg_location"] = ffmpeg_loc
    with YoutubeDL(opts) as ydl:
        ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
    files = glob.glob(os.path.join(tmpdir, "*.mp3"))
    if not files:
        raise TrackNotFound("MP3 hosil bo'lmadi")
    return files[0]


def _reencode(path: str, bitrate: str) -> str:
    out = path.rsplit(".", 1)[0] + f".{bitrate}k.mp3"
    ffmpeg_bin = _ffmpeg_location()
    ffmpeg_exe = os.path.join(ffmpeg_bin, "ffmpeg.exe") if ffmpeg_bin else "ffmpeg"
    subprocess.run(
        [ffmpeg_exe, "-y", "-loglevel", "error", "-i", path, "-b:a", f"{bitrate}k", out],
        check=True,
        timeout=120,
    )
    os.remove(path)
    return out


def _tag(path: str, track: Track, cover: bytes | None) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("TIT2")
    tags.delall("TPE1")
    tags.add(TIT2(encoding=3, text=track.title))
    tags.add(TPE1(encoding=3, text=track.artists))
    if track.album:
        tags.add(TALB(encoding=3, text=track.album))
    if track.year:
        tags.add(TDRC(encoding=3, text=track.year))
    if track.track_no:
        tags.add(TRCK(encoding=3, text=str(track.track_no)))
    if cover:
        tags.delall("APIC")
        tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover))
    tags.save(path, v2_version=3)


async def _fetch_cover(url: str) -> bytes | None:
    if not url:
        return None
    try:
        session = await spotify.session()
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status == 200:
                data = await resp.read()
                if len(data) > 5 * 1024 * 1024:
                    return None
                return data
    except Exception:
        log.debug("Muqova olib bo'lmadi: %s", url)
    return None


async def download(track: Track, bitrate: str, tmpdir: str) -> Downloaded:
    video_id = track.video_id or await matcher.find_video_id(track)
    if not video_id:
        raise TrackNotFound(track.full_name)

    if bitrate == "320" and track.duration > LONG_TRACK_SECONDS:
        bitrate = "128"

    cover_url, thumb_url = track.cover_url, track.thumb_url
    if not cover_url and not track.id.startswith("yt:"):
        cover_url = thumb_url = await spotify.oembed_thumb(track.id)

    async with _download_sem:
        loop = asyncio.get_running_loop()
        path_task = loop.run_in_executor(
            _executor, _ydl_download, video_id, tmpdir, bitrate
        )
        cover_task = asyncio.create_task(_fetch_cover(cover_url))
        thumb_task = asyncio.create_task(_fetch_cover(thumb_url))
        try:
            path = await path_task
        except TrackNotFound:
            raise
        except Exception as e:
            log.warning("yt-dlp xatosi %s: %s", track.full_name, e)
            raise TrackNotFound(track.full_name) from e
        cover = await cover_task
        thumb = await thumb_task

    if os.path.getsize(path) > MAX_SIZE:
        if bitrate != "128":
            loop = asyncio.get_running_loop()
            path = await loop.run_in_executor(_executor, _reencode, path, "128")
        if os.path.getsize(path) > MAX_SIZE:
            raise TooLarge(track.full_name)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _tag, path, track, cover)

    thumb_path = None
    if thumb:
        thumb_path = os.path.join(tmpdir, "thumb.jpg")
        with open(thumb_path, "wb") as f:
            f.write(thumb)

    return Downloaded(mp3_path=path, thumb_path=thumb_path)
