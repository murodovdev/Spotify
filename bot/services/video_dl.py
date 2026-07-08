"""Social media video download service backed by yt-dlp.

Supports: Instagram, TikTok, YouTube/Shorts, Facebook, X/Twitter, Pinterest, Vimeo.
All blocking yt-dlp calls are off-loaded to a thread executor.
"""

import asyncio
import logging
import os
import re
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from bot.services import tg_limits, ytdlp_common

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
# Shorts eski oqimda qoladi (darhol audio) — format tanlash faqat oddiy videolar uchun.
_YT_SHORTS_RE = re.compile(
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
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

# Yuklash chegaralari API rejimiga bog'liq — bot/services/tg_limits.py.


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
    ytdlp_common.apply(ydl_opts)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if not info:
        raise ValueError("yt-dlp returned no metadata")

    video_path = _find_output(tmpdir, info)
    if not video_path:
        raise FileNotFoundError("Downloaded file not found in tmpdir")

    size = os.path.getsize(video_path)
    if size > tg_limits.max_upload_bytes():
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
    ytdlp_common.apply(ydl_opts)

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


def is_yt_shorts(text: str) -> bool:
    return _YT_SHORTS_RE.search(text) is not None


# ─── Audio format tanlovi (standart YouTube videolari uchun) ─────────────────

class YTError(Exception):
    """yt-dlp xatosi, foydalanuvchiga ko'rsatiladigan sabab kodi bilan.

    reason: private | deleted | geo | live | age | network | generic
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


class YTTooLarge(Exception):
    pass


def classify_yt_error(exc: Exception) -> str:
    """yt-dlp xato matnini foydalanuvchiga tushunarli sababga aylantiradi.

    Tartib muhim: geo/age xabarlari ham "unavailable" so'zini o'z ichiga olishi
    mumkin, shuning uchun aniqroq shablonlar avval tekshiriladi.
    """
    msg = str(exc).lower()
    if "private" in msg:
        return "private"
    if "live event" in msg or "is live" in msg or "premieres in" in msg:
        return "live"
    if "confirm your age" in msg or "age-restricted" in msg or "inappropriate" in msg:
        return "age"
    if "in your country" in msg or "geo" in msg or "not available in your" in msg:
        return "geo"
    if "removed" in msg or "deleted" in msg or "does not exist" in msg or "unavailable" in msg:
        return "deleted"
    if "timed out" in msg or "connection" in msg or "temporary failure" in msg:
        return "network"
    return "generic"


# Har bir format aniq bir maqsad uchun: MP3 — universal moslik, M4A — manba
# oqimi qayta kodlanmasdan, FLAC — yo'qotishsiz konteyner, OPUS — eng yaxshi
# sifat/hajm nisbati. `pp` = None bo'lsa ffmpeg qayta kodlamaydi.
FMT_MP3, FMT_M4A, FMT_FLAC, FMT_OPUS = "mp3", "m4a", "flac", "opus"
FMT_ORDER = (FMT_MP3, FMT_M4A, FMT_FLAC, FMT_OPUS)

# Taxminiy hajm tartibi (kichikdan kattaga). Fayl chegaradan oshsa foydalanuvchiga
# faqat shu ro'yxatda *pastroq* turgan formatlar taklif qilinadi.
_FMT_SIZE_RANK = {FMT_OPUS: 1, FMT_M4A: 2, FMT_MP3: 3, FMT_FLAC: 4}


def smaller_formats(fmt: str, available: tuple[str, ...]) -> tuple[str, ...]:
    """`fmt` chegaradan oshgach taklif qilinadigan kichikroq formatlar."""
    rank = _FMT_SIZE_RANK.get(fmt, 0)
    return tuple(f for f in available if f != fmt and _FMT_SIZE_RANK.get(f, 99) < rank)


# Telegram audio pleyeri faqat mp3/m4a ni tanidi — qolganlari hujjat sifatida.
AUDIO_FORMATS = frozenset({FMT_MP3, FMT_M4A})

_FMT_SELECTOR = {
    FMT_MP3: "bestaudio/best",
    FMT_M4A: "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]",
    FMT_FLAC: "bestaudio/best",
    FMT_OPUS: "bestaudio[acodec^=opus]/bestaudio[ext=webm]",
}
# preferredcodec — None bo'lsa FFmpegExtractAudio umuman qo'shilmaydi.
_FMT_CODEC = {
    FMT_MP3: "mp3",
    FMT_M4A: None,
    FMT_FLAC: "flac",
    FMT_OPUS: "opus",
}


def _available_formats(info: dict) -> tuple[str, ...]:
    """Video uchun haqiqatan ham mavjud formatlar.

    mp3/flac har doim mumkin (istalgan audio oqimidan ffmpeg konvertatsiya
    qiladi). m4a va opus esa manbada mos oqim bo'lsagina ko'rsatiladi —
    aks holda ular qayta kodlashni talab qiladi va "original"/"lossless"
    va'dasi yolg'on bo'lib qoladi.
    """
    has_m4a = has_opus = False
    for f in info.get("formats") or []:
        acodec = (f.get("acodec") or "").lower()
        if not acodec or acodec == "none":
            continue
        if f.get("ext") == "m4a" or acodec.startswith("mp4a"):
            has_m4a = True
        if acodec.startswith("opus"):
            has_opus = True

    out = [FMT_MP3]
    if has_m4a:
        out.append(FMT_M4A)
    out.append(FMT_FLAC)
    if has_opus:
        out.append(FMT_OPUS)
    return tuple(out)


@dataclass
class YTVideoMeta:
    video_id: str
    title: str
    channel: str
    duration: int
    thumbnail: str
    formats: tuple[str, ...] = ()
    is_live: bool = False


def _ydl_extract_meta(video_id: str) -> YTVideoMeta:
    import yt_dlp
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
    }
    ytdlp_common.apply(opts)
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:  # yt_dlp.utils.DownloadError va boshqalar
        raise YTError(classify_yt_error(e), str(e)) from e
    if not info:
        raise YTError("generic", "No metadata returned")
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise YTError("live")

    return YTVideoMeta(
        video_id=video_id,
        title=info.get("title") or "",
        channel=info.get("uploader") or info.get("channel") or "",
        duration=int(info.get("duration") or 0),
        thumbnail=info.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        formats=_available_formats(info),
    )


def _ydl_download_yt_audio(video_id: str, fmt: str, tmpdir: str) -> str:
    """Tanlangan formatda audio yuklaydi. Qaytaradi: fayl yo'li."""
    import yt_dlp

    from bot.services.downloader import _ffmpeg_location

    codec = _FMT_CODEC[fmt]
    pps: list[dict] = []
    if codec:
        pp = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
        if codec == "mp3":
            pp["preferredquality"] = "0"  # eng yuqori VBR
        pps.append(pp)
    # Teglar va muqova — imkon qadar (EmbedThumbnail mp3/m4a/flac/opus'ni qo'llab-quvvatlaydi).
    pps.append({"key": "FFmpegMetadata", "add_metadata": True})
    pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    opts: dict = {
        "format": _FMT_SELECTOR[fmt],
        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
        "postprocessors": pps,
        "writethumbnail": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 3,
        "socket_timeout": 30,
    }
    ytdlp_common.apply(opts)
    ffmpeg_loc = _ffmpeg_location()
    if ffmpeg_loc:
        opts["ffmpeg_location"] = ffmpeg_loc

    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as e:
        raise YTError(classify_yt_error(e), str(e)) from e

    # Muqova fayllari (.jpg/.webp) hisobga olinmasin — faqat audio kengaytmalari.
    exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".webm", ".mp4")
    best, best_size = None, 0
    for fn in os.listdir(tmpdir):
        if not fn.lower().endswith(exts):
            continue
        fp = os.path.join(tmpdir, fn)
        sz = os.path.getsize(fp)
        if sz > best_size:
            best, best_size = fp, sz
    if not best:
        raise YTError("generic", "Audio fayl topilmadi")
    if best_size > tg_limits.max_upload_bytes():
        raise YTTooLarge(f"{best_size // 1_048_576} MB")
    return best


async def download_yt_audio(video_id: str, fmt: str, tmpdir: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _ydl_download_yt_audio, video_id, fmt, tmpdir)


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
    ytdlp_common.apply(opts)
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


# Metadata keshi: preview ko'rsatilgach foydalanuvchi format tanlaguncha o'tgan
# vaqt ichida yt-dlp'ga qayta murojaat qilmaslik uchun. Qisqa TTL — YouTube
# javoblari (formatlar) tez eskiradi.
_META_TTL = 600.0
_META_MAX = 256
_meta_cache: "OrderedDict[str, tuple[float, YTVideoMeta]]" = OrderedDict()


async def get_yt_meta(video_id: str) -> YTVideoMeta:
    """Keshlangan metadata; muddati o'tgan yoki yo'q bo'lsa — yt-dlp'dan."""
    now = time.monotonic()
    hit = _meta_cache.get(video_id)
    if hit and now - hit[0] < _META_TTL:
        _meta_cache.move_to_end(video_id)
        return hit[1]

    meta = await extract_yt_meta(video_id)
    _meta_cache[video_id] = (now, meta)
    _meta_cache.move_to_end(video_id)
    while len(_meta_cache) > _META_MAX:
        _meta_cache.popitem(last=False)
    return meta


async def extract_yt_playlist(playlist_id: str) -> YTPlaylistMeta:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _ydl_extract_playlist, playlist_id)
