"""Shazam-powered audio fingerprinting service.

Accepts any media path → extracts optimal audio segment → queries Shazam API
→ returns structured recognition result or None.
"""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="recognizer")


@lru_cache(maxsize=1)
def _ffmpeg() -> str:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    winget = (
        r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
    )
    return winget if os.path.isfile(winget) else "ffmpeg"


@lru_cache(maxsize=1)
def _ffprobe() -> str:
    if shutil.which("ffprobe"):
        return "ffprobe"
    winget = (
        r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.1.2-full_build\bin\ffprobe.exe"
    )
    return winget if os.path.isfile(winget) else "ffprobe"


def _get_duration(path: str) -> float:
    try:
        result = subprocess.run(
            [
                _ffprobe(), "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        raw = result.stdout.strip()
        return float(raw) if raw else 0.0
    except Exception:
        return 0.0


def _extract_segment(src: str, dst: str, start: float, duration: float) -> bool:
    """Extract an audio segment as mono WAV at 44100 Hz using FFmpeg."""
    try:
        subprocess.run(
            [
                _ffmpeg(), "-y", "-loglevel", "error",
                "-ss", str(start), "-i", src,
                "-t", str(duration),
                "-vn", "-ac", "1", "-ar", "44100",
                "-f", "wav", dst,
            ],
            check=True, timeout=60,
        )
        return os.path.exists(dst) and os.path.getsize(dst) > 1000
    except Exception as e:
        log.debug("FFmpeg extract failed: %s", e)
        return False


def _preprocess(src: str, dst: str) -> bool:
    """Extract the best ~30-second segment for fingerprinting.

    Skips the first 10–20% of the track to avoid intros and silence.
    Falls back gracefully for short clips.
    """
    dur = _get_duration(src)

    if dur <= 0:
        # Unknown duration — try from start, hope for the best
        return _extract_segment(src, dst, 0.0, 30.0)

    if dur <= 35.0:
        # Short clip — use the whole thing
        return _extract_segment(src, dst, 0.0, dur)

    # Skip intro: start at ~20% of track (min 10 s) and take 30 s
    start = max(10.0, dur * 0.20)
    clip = min(30.0, dur - start)
    return _extract_segment(src, dst, start, clip)


def _parse(result: dict) -> dict | None:
    """Parse Shazam API response into a clean recognition dict."""
    track = result.get("track")
    if not track:
        return None

    title = track.get("title") or ""
    artist = track.get("subtitle") or ""
    if not title or not artist:
        return None

    # Extract metadata from the SONG section
    sections = track.get("sections") or []
    meta: dict[str, str] = {}
    for section in sections:
        if section.get("type") == "SONG":
            for item in section.get("metadata") or []:
                k = (item.get("title") or "").lower()
                v = item.get("text") or ""
                if k and v:
                    meta[k] = v

    released = meta.get("released", "")
    year = released[:4] if released else ""

    genres = track.get("genres") or {}
    genre = genres.get("primary") or ""

    images = track.get("images") or {}
    cover = images.get("coverarthq") or images.get("coverart") or ""

    share = track.get("share") or {}
    share_url = share.get("href") or ""

    return {
        "title": title,
        "artist": artist,
        "album": meta.get("album", ""),
        "year": year,
        "genre": genre,
        "cover": cover,
        "share_url": share_url,
    }


async def recognize(media_path: str) -> dict | None:
    """Identify a song from any media file.

    Downloads the file, preprocesses it with FFmpeg, and queries the Shazam API.
    Returns a dict with keys: title, artist, album, year, genre, cover, share_url.
    Returns None if the song could not be identified.
    """
    try:
        from shazamio import Shazam  # type: ignore[import]
    except ImportError:
        log.error("shazamio not installed — music recognition unavailable. Run: pip install shazamio")
        return None

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        loop = asyncio.get_running_loop()
        ok = await loop.run_in_executor(_executor, _preprocess, media_path, wav_path)
        if not ok:
            log.warning("Audio preprocessing failed for: %s", media_path)
            return None

        shazam = Shazam()
        result = await shazam.recognize(wav_path)
        return _parse(result)
    except Exception as e:
        log.warning("Shazam recognition failed: %s", e)
        return None
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass
