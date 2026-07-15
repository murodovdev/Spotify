"""yt-dlp uchun umumiy sozlamalar: player_client, PO token, proxy va aria2c.

yt-dlp 2026.07+ YouTube signature/n-challenge uchun JS runtime (deno) talab
qiladi. Bot-detection'ga qarshi qatlamlar:
  1. bgutil PO token plagini (avtomatik, bot/services/pot_provider.py serveri);
  2. YT_PO_TOKEN env — qo'lda berilgan token (plagindan ustuvor);
  3. YTDLP_PROXY env — residential proxy URL (IP butunlay bloklangan holat uchun);
  4. YTDLP_VERBOSE=1 env — yt-dlp'ning to'liq debug logi (POT oqimini ko'rsatadi).
"""

import logging
import os
import shutil

log = logging.getLogger(__name__)

# web birinchi: PO token (bgutil provider) faqat web-oilasi klientlariga
# beriladi — android_vr token ishlatmaydi, u IP toza bo'lgandagina ishlaydi.
_CLIENTS = ["web", "android_vr"]

_HAS_ARIA2C: bool | None = None
_PO_TOKEN: str | None = None
_PO_LOADED = False
_PLUGIN_CHECKED = False

_VERBOSE = os.getenv("YTDLP_VERBOSE", "").strip() == "1"
_PROXY = os.getenv("YTDLP_PROXY", "").strip()


def _check_plugin() -> None:
    """bgutil plagini yt-dlp'ga ko'rinishini bir marta tekshirib log qiladi."""
    global _PLUGIN_CHECKED
    if _PLUGIN_CHECKED:
        return
    _PLUGIN_CHECKED = True
    try:
        import yt_dlp_plugins.extractor.getpot_bgutil_http  # noqa: F401
        log.info("bgutil yt-dlp plagini topildi (HTTP provider)")
    except ImportError as e:
        log.warning("bgutil yt-dlp plagini YO'Q — PO token ishlatilmaydi: %s", e)


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
    """yt-dlp opts'ga umumiy sozlamalarni qo'shadi (idempotent)."""
    _check_plugin()

    ea = opts.setdefault("extractor_args", {})
    yt = ea.setdefault("youtube", {})
    yt.setdefault("player_client", list(_CLIENTS))

    token = _po_token()
    if token and "po_token" not in yt:
        yt["po_token"] = [token]

    if _PROXY and "proxy" not in opts:
        opts["proxy"] = _PROXY

    if _VERBOSE:
        opts["verbose"] = True
        opts["quiet"] = False
        opts["no_warnings"] = False

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
