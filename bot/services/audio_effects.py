"""FFmpeg-based audio effects for post-download processing."""

import asyncio
import logging
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fx")

EFFECTS: dict[str, str] = {
    "8d":        "🎧 8D Audio",
    "bass":      "🔊 Bass Boost",
    "reverb":    "🌌 Reverb",
    "acoustic":  "🎵 Acoustic",
    "vocal":     "🎤 Vocal Boost",
    "slowed":    "🎶 Slowed",
    "nightcore": "⚡ Nightcore",
    "lofi":      "🌙 Lo-Fi",
}

# FFmpeg audio filter chains per effect
_FILTERS: dict[str, str] = {
    "8d":        "apulsator=hz=0.125",
    "bass":      "equalizer=f=50:t=h:w=100:g=8,equalizer=f=100:t=h:w=100:g=4",
    "reverb":    "aecho=0.8:0.88:60:0.4",
    "acoustic":  "equalizer=f=200:t=h:w=200:g=3,equalizer=f=4000:t=h:w=2000:g=2,equalizer=f=60:t=h:w=100:g=-3",
    "vocal":     "equalizer=f=1500:t=h:w=1000:g=5,equalizer=f=3000:t=h:w=2000:g=3",
    "slowed":    "atempo=0.85,aecho=0.8:0.88:20:0.3",
    "nightcore": "asetrate=44100*1.25,aresample=44100",
    "lofi":      "lowpass=f=3500,equalizer=f=100:t=h:w=100:g=4,aecho=0.6:0.5:20:0.2",
}


@lru_cache(maxsize=1)
def _ffmpeg_exe() -> str:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    winget_bin = (
        r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.1.2-full_build\bin"
    )
    exe = os.path.join(winget_bin, "ffmpeg.exe")
    return exe if os.path.isfile(exe) else "ffmpeg"


def _apply_sync(input_path: str, output_path: str, effect: str) -> None:
    af = _FILTERS[effect]
    subprocess.run(
        [
            _ffmpeg_exe(), "-y", "-loglevel", "error",
            "-i", input_path,
            "-af", af,
            "-map_metadata", "0",
            "-id3v2_version", "3",
            "-b:a", "192k",
            output_path,
        ],
        check=True,
        timeout=180,
    )


async def apply_effect(input_path: str, output_path: str, effect: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _apply_sync, input_path, output_path, effect)
