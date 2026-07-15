"""yt-dlp uchun umumiy sozlamalar: player_client, fallback va aria2c tezlashtirish.

yt-dlp 2026.07+ YouTube signature/n-challenge uchun JS runtime (deno) talab
qiladi. `android_vr` asosiy klient — PO token yoki cookies'siz ishlaydi.
`web` fallback sifatida: android_vr bot-detect qilsa yt-dlp avtomatik sinaydi.
"""

import logging
import shutil

log = logging.getLogger(__name__)

_CLIENTS = ["android_vr", "web"]

_HAS_ARIA2C: bool | None = None


def _aria2c_available() -> bool:
    global _HAS_ARIA2C
    if _HAS_ARIA2C is None:
        _HAS_ARIA2C = shutil.which("aria2c") is not None
        if _HAS_ARIA2C:
            log.info("aria2c topildi — tezlashtirilgan yuklab olish yoqildi")
        else:
            log.info("aria2c topilmadi — standart HTTP downloader ishlatiladi")
    return _HAS_ARIA2C


def apply(opts: dict) -> dict:
    """yt-dlp opts'ga player_client va aria2c sozlamalarini qo'shadi (idempotent)."""
    ea = opts.setdefault("extractor_args", {})
    ea.setdefault("youtube", {}).setdefault("player_client", list(_CLIENTS))

    if _aria2c_available() and "external_downloader" not in opts:
        opts["external_downloader"] = {"default": "aria2c"}
        opts["external_downloader_args"] = {
            "aria2c": [
                "--min-split-size=1M",
                "--max-connection-per-server=16",
                "--split=16",
                "--max-concurrent-downloads=1",
                "--file-allocation=none",
                "--allow-overwrite=true",
                "--auto-file-renaming=false",
                "--console-log-level=error",
            ]
        }
    return opts
