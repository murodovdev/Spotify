"""yt-dlp uchun umumiy sozlamalar: player_client, PO token va aria2c.

yt-dlp 2026.07+ YouTube signature/n-challenge uchun JS runtime (deno) talab
qiladi. `android_vr` asosiy klient. YouTube bot-detect qilsa PO token kerak:
  YT_PO_TOKEN=WEB+AbCd...  env o'zgaruvchisi orqali beriladi.
"""

import logging
import os
import shutil

log = logging.getLogger(__name__)

_CLIENTS = ["android_vr", "web"]

_HAS_ARIA2C: bool | None = None
_PO_TOKEN: str | None = None
_PO_LOADED = False


def _aria2c_available() -> bool:
    global _HAS_ARIA2C
    if _HAS_ARIA2C is None:
        _HAS_ARIA2C = shutil.which("aria2c") is not None
        if _HAS_ARIA2C:
            log.info("aria2c topildi — tezlashtirilgan yuklab olish yoqildi")
        else:
            log.info("aria2c topilmadi — standart HTTP downloader ishlatiladi")
    return _HAS_ARIA2C


def _po_token() -> str | None:
    global _PO_TOKEN, _PO_LOADED
    if not _PO_LOADED:
        _PO_TOKEN = os.getenv("YT_PO_TOKEN") or None
        _PO_LOADED = True
        if _PO_TOKEN:
            log.info("YouTube PO token yuklandi")
    return _PO_TOKEN


def apply(opts: dict) -> dict:
    """yt-dlp opts'ga player_client, PO token va aria2c sozlamalarini qo'shadi."""
    ea = opts.setdefault("extractor_args", {})
    yt = ea.setdefault("youtube", {})
    yt.setdefault("player_client", list(_CLIENTS))

    token = _po_token()
    if token and "po_token" not in yt:
        yt["po_token"] = [token]

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
