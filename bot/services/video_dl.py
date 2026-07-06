"""Social media video download service backed by yt-dlp.

Supports: Instagram, TikTok, YouTube/Shorts, Facebook, X/Twitter, Pinterest, Vimeo.
All blocking yt-dlp calls are off-loaded to a thread executor.
"""

import asyncio
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="video_dl")

_YT_RE = re.compile(
    r"(?:https?://)?(?:(?:www\.|music\.)?youtube\.com/"
    r"(?:watch\?(?:.*&)?v=|shorts/|live/)|youtu\.be/)([\w-]+)",
    re.IGNORECASE,
)
_YT_PLAYLIST_RE = re.compile(
    r"(?:https?://)?(?:(?:www\.|music\.)?youtube\.com/"
    r"(?:playlist\?|watch\?.*&?)list=)([\w-]+)",
    re.IGNORECASE,
)

# (platform_name, compiled_pattern)
_PLATFORMS: list[tuple[str, re.Pattern]] = [
    ("Instagram", re.compile(
        r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv)/[\w-]+",
        re.IGNORECASE,
    )),
    ("TikTok", re.compile(
        r"(?:https?://)?(?:(?:www|vm|vt|m)\.)?tiktok\.com/"
        r"(?:@[\w.]+/video/\d+|v/\d+|[\w]{5,})",
        re.IGNORECASE,
    )),
    ("YouTube", re.compile(
        r"(?:https?://)?(?:(?:www\.|music\.)?youtube\.com/"
        r"(?:watch\?(?:.*&)?v=|shorts/|live/)|youtu\.be/)[\w-]+",
        re.IGNORECASE,
    )),
    ("Facebook", re.compile(
        r"(?:https?://)?(?:www\.|m\.)?(?:"
        r"facebook\.com/(?:watch/?|videos/|reel/|\w+/videos/)|"
        r"fb\.watch/)[\w?=&%./-]+",
        re.IGNORECASE,
    )),
    ("X/Twitter", re.compile(
        r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/\w+/status/\d+",
        re.IGNORECASE,
    )),
    ("Pinterest", re.compile(
        r"(?:https?://)?(?:www\.)?(?:pinterest\.com/pin/[\d-]+|pin\.it/\w+)",
        re.IGNORECASE,
    )),
    ("Vimeo", re.compile(
        r"(?:https?://)?(?:www\.)?vimeo\.com/\d+",
        re.IGNORECASE,
    )),
]

# 50 MB — Telegram bot video upload limit
MAX_VIDEO_BYTES = 50 * 1024 * 1024


@dataclass
class VideoInfo:
    title: str
    duration: int           # seconds
    thumbnail_url: str
    video_path: str
    platform: str = field(default="")


def extract_video_url(text: str) -> tuple[str, str] | None:
    """Return (url, platform_name) for the first social video URL found in text, or None."""
    for name, pattern in _PLATFORMS:
        m = pattern.search(text)
        if m:
            return m.group(), name
    return None


# ─── Blocking helpers ─────────────────────────────────────────────────────────

def _find_output(tmpdir: str, info: dict) -> str | None:
    """Locate the downloaded file, trying multiple fallback strategies."""
    # Strategy 1: requested_downloads in info dict
    for dl in info.get("requested_downloads") or []:
        fp = dl.get("filepath") or dl.get("filename") or ""
        if fp and os.path.isfile(fp):
            return fp

    # Strategy 2: scan tmpdir for the largest file
    best = None
    best_size = 0
    for fn in os.listdir(tmpdir):
        fp = os.path.join(tmpdir, fn)
        if os.path.isfile(fp):
            sz = os.path.getsize(fp)
            if sz > best_size:
                best_size = sz
                best = fp

    return best if best_size > 10_000 else None


def _ydl_download_video(url: str, tmpdir: str) -> VideoInfo:
    """Blocking yt-dlp download. Raises ValueError / FileNotFoundError on failure."""
    import yt_dlp  # type: ignore[import]

    # Prefer 720p MP4 to keep file size manageable; fall back to best available.
    fmt = (
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=720]+bestaudio"
        "/best[height<=720][ext=mp4]"
        "/best[height<=720]"
        "/best"
    )

    ydl_opts: dict = {
        "format": fmt,
        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if not info:
        raise ValueError("yt-dlp returned no metadata")

    video_path = _find_output(tmpdir, info)
    if not video_path:
        raise FileNotFoundError("Downloaded file not found in tmpdir")

    size = os.path.getsize(video_path)
    if size > MAX_VIDEO_BYTES:
        raise ValueError(f"Video too large ({size // 1_048_576} MB)")

    return VideoInfo(
        title=info.get("title") or "",
        duration=int(info.get("duration") or 0),
        thumbnail_url=info.get("thumbnail") or "",
        video_path=video_path,
    )


def _ydl_download_audio(url: str, tmpdir: str) -> str:
    """Blocking yt-dlp audio-only download. Returns the audio file path."""
    import yt_dlp  # type: ignore[import]

    ydl_opts: dict = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "outtmpl": os.path.join(tmpdir, "audio.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if not info:
        raise ValueError("yt-dlp returned no metadata for audio")

    audio_path = _find_output(tmpdir, info)
    if not audio_path:
        raise FileNotFoundError("Audio file not found in tmpdir")

    return audio_path


# ─── Async wrappers ───────────────────────────────────────────────────────────

async def download_video(url: str, platform: str, tmpdir: str) -> VideoInfo:
    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(_executor, _ydl_download_video, url, tmpdir)
    info.platform = platform
    return info


async def download_audio(url: str, tmpdir: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _ydl_download_audio, url, tmpdir)


# ─── YouTube helpers ─────────────────────────────────────────────────────────

def extract_yt_video_id(text: str) -> str | None:
    m = _YT_RE.search(text)
    return m.group(1) if m else None


def extract_yt_playlist_id(text: str) -> str | None:
    m = _YT_PLAYLIST_RE.search(text)
    return m.group(1) if m else None


def is_youtube_url(text: str) -> bool:
    return _YT_RE.search(text) is not None


@dataclass
class YTVideoMeta:
    video_id: str
    title: str
    channel: str
    duration: int
    thumbnail: str


def _ydl_extract_meta(video_id: str) -> YTVideoMeta:
    import yt_dlp
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 20,
        "extractor_args": {"youtube": {"player_client": ["android", "web_safari"]}},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=False,
        )
    if not info:
        raise ValueError("No metadata returned")
    return YTVideoMeta(
        video_id=video_id,
        title=info.get("title") or "",
        channel=info.get("uploader") or info.get("channel") or "",
        duration=int(info.get("duration") or 0),
        thumbnail=info.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    )


@dataclass
class YTPlaylistMeta:
    playlist_id: str
    title: str
    channel: str
    entries: list[YTVideoMeta]


def _ydl_extract_playlist(playlist_id: str) -> YTPlaylistMeta:
    import yt_dlp
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "socket_timeout": 20,
    }
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise ValueError("No playlist metadata returned")

    entries: list[YTVideoMeta] = []
    for e in info.get("entries") or []:
        if not e:
            continue
        vid = e.get("id") or e.get("url") or ""
        entries.append(YTVideoMeta(
            video_id=vid,
            title=e.get("title") or "",
            channel=e.get("uploader") or e.get("channel") or info.get("uploader") or "",
            duration=int(e.get("duration") or 0),
            thumbnail=e.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        ))
    return YTPlaylistMeta(
        playlist_id=playlist_id,
        title=info.get("title") or "YouTube Playlist",
        channel=info.get("uploader") or info.get("channel") or "",
        entries=entries,
    )


async def extract_yt_meta(video_id: str) -> YTVideoMeta:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _ydl_extract_meta, video_id)


async def extract_yt_playlist(playlist_id: str) -> YTPlaylistMeta:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _ydl_extract_playlist, playlist_id)
