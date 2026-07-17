"""yt-dlp uchun umumiy sozlamalar: player_client, cookie, PO token, proxy, aria2c.

yt-dlp 2026.07+ YouTube signature/n-challenge uchun JS runtime (deno) talab
qiladi. Datacenter IP'da ("Sign in to confirm you're not a bot") bot-detection'ga
qarshi qatlamlar — ishonchlilik tartibida:

  1. YT_COOKIES / YT_COOKIES_FILE — login qilingan (afzali burner) YouTube
     akkaunt cookie'lari. ENG ishonchli yechim: yt-dlp autentifikatsiya
     qilinganida bot-tekshiruv deyarli yo'qoladi va chidamli klientlar
     (tv_downgraded, web_safari) ishlatiladi. Railway'da YT_COOKIES env'ga
     cookies.txt matnini qo'ying — startupda /tmp faylga yoziladi.
  2. bgutil PO token plagini (avtomatik, bot/services/pot_provider.py serveri)
     — GVS/streaming URL uchun token yaratadi; cookie bilan birga ishlaydi.
  3. YT_PO_TOKEN env — qo'lda berilgan token (plagindan ustuvor).
  4. YTDLP_PROXY env — residential proxy URL (IP butunlay bloklangan holat uchun).
  5. YTDLP_PLAYER_CLIENT env — player_client'ni qo'lda ustun qilish (vergul bilan).
  6. YTDLP_VERBOSE=1 env — yt-dlp'ning to'liq debug logi (POT oqimini ko'rsatadi).
"""

import importlib.util
import logging
import os
import shutil
import tempfile

log = logging.getLogger(__name__)

# Klient tanlovi (bir nechta video bilan empirik tekshirilgan, POT + yt-dlp-ejs
# bilan). YouTube endi ko'p klientlarga SABR streamingни majburlaydi (yt-dlp
# #12482) — bunday klientlar (web/web_safari/tv) yuklab bo'lmaydigan yoki 403
# beradigan formatlar qaytaradi. Haqiqatan yuklab olinadigan m4a formatni:
#   * mweb — cookie bilan (GVS POT + challenge solver kerak);
#   * android_vr — cookiesiz (JS player talab qilmaydi, faqat GVS POT).
# beradi. web_safari faqat ikkilamchi zaxira sifatida qoldirilgan (SABR
# formatlari o'tkazib yuboriladi, lekin ba'zi videolar uchun manba bo'lishi
# mumkin). Eski "tv/web" tanlovi 403 va "format mavjud emas" berardi.
_CLIENTS_WITH_COOKIES = ["mweb", "web_safari"]
_CLIENTS_NO_COOKIES = ["android_vr", "mweb"]

_HAS_ARIA2C: bool | None = None
_PO_TOKEN: str | None = None
_PO_LOADED = False
_PLUGIN_CHECKED = False
_COOKIE_FILE: str | None = None
_COOKIE_LOADED = False

_VERBOSE = os.getenv("YTDLP_VERBOSE", "").strip() == "1"
_PROXY = os.getenv("YTDLP_PROXY", "").strip()
_CLIENT_OVERRIDE = [
    c.strip() for c in os.getenv("YTDLP_PLAYER_CLIENT", "").split(",") if c.strip()
]


def _check_plugin() -> None:
    """bgutil plagini yt-dlp'ga ko'rinishini bir marta tekshirib log qiladi."""
    global _PLUGIN_CHECKED
    if _PLUGIN_CHECKED:
        return
    _PLUGIN_CHECKED = True
    try:
        # import emas, find_spec: modul shu yerda exec bo'lsa provider registrga
        # kiradi va yt-dlp o'z loaderi bilan qayta yuklaganda
        # "PoTokenProvider BgUtilHTTP already registered" xatosi chiqadi.
        spec = importlib.util.find_spec("yt_dlp_plugins.extractor.getpot_bgutil_http")
    except ImportError as e:
        log.warning("bgutil yt-dlp plagini YO'Q — PO token ishlatilmaydi: %s", e)
        return
    if spec is not None:
        log.info("bgutil yt-dlp plagini topildi (HTTP provider)")
    else:
        log.warning("bgutil yt-dlp plagini YO'Q — PO token ishlatilmaydi")


def _cookie_file() -> str | None:
    """Cookie faylini bir marta tayyorlaydi (env matnidan yoki tayyor fayldan)."""
    global _COOKIE_FILE, _COOKIE_LOADED
    if _COOKIE_LOADED:
        return _COOKIE_FILE
    _COOKIE_LOADED = True

    path = os.getenv("YT_COOKIES_FILE", "").strip()
    if path:
        if os.path.isfile(path):
            _COOKIE_FILE = path
            log.info("YouTube cookie fayli ishlatiladi: %s", path)
        else:
            log.warning("YT_COOKIES_FILE topilmadi: %s", path)
        return _COOKIE_FILE

    content = os.getenv("YT_COOKIES", "")
    if content.strip():
        # Netscape cookies.txt formati tab bilan ishlaydi; ba'zi env muharrirlar
        # tablarni buzadi, shuning uchun matnni o'zgartirmasdan yozamiz.
        fd, tmp = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content if content.endswith("\n") else content + "\n")
        _COOKIE_FILE = tmp
        log.info("YouTube cookie'lari env'dan yozildi (%s)", tmp)
    return _COOKIE_FILE


def _clients() -> list[str]:
    if _CLIENT_OVERRIDE:
        return list(_CLIENT_OVERRIDE)
    return list(_CLIENTS_WITH_COOKIES if _cookie_file() else _CLIENTS_NO_COOKIES)


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
    yt.setdefault("player_client", _clients())

    cookies = _cookie_file()
    if cookies and "cookiefile" not in opts:
        opts["cookiefile"] = cookies

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
