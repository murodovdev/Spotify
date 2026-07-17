"""yt-dlp uchun umumiy sozlamalar: player_client, cookie, PO token, proxy, aria2c.

yt-dlp 2026.07+ YouTube signature/n-challenge uchun JS runtime (deno) talab
qiladi. Datacenter IP'da ("Sign in to confirm you're not a bot") bot-detection'ga
qarshi qatlamlar — ishonchlilik tartibida:

  1. YT_COOKIES_B64 (TAVSIYA) / YT_COOKIES / YT_COOKIES_FILE — login qilingan
     (afzali burner) YouTube akkaunt cookie'lari. ENG ishonchli yechim: yt-dlp
     autentifikatsiya qilinganida bot-tekshiruv yo'qoladi.
     TUZOQ: Netscape cookies.txt TAB bilan ajratiladi, Railway kabi env
     maydonlari tab'ni bo'sh joyga aylantiradi → yt-dlp 0 ta cookie o'qiydi va
     JIMGINA cookie'siz davom etadi ("not a bot" qaytadi). Shu sabab
     YT_COOKIES_B64 (base64) afzal; xom YT_COOKIES berilsa tab'lar avtomatik
     tiklanadi va o'qilgan cookie soni loglanadi.
  2. bgutil PO token plagini (avtomatik, bot/services/pot_provider.py serveri)
     — GVS/streaming URL uchun token yaratadi; cookie bilan birga ishlaydi.
  3. YT_PO_TOKEN env — qo'lda berilgan token (plagindan ustuvor).
  4. YTDLP_PROXY env — residential proxy URL (IP butunlay bloklangan holat uchun).
  5. YTDLP_PLAYER_CLIENT env — player_client'ni qo'lda ustun qilish (vergul bilan).
  6. YTDLP_VERBOSE=1 env — yt-dlp'ning to'liq debug logi (POT oqimini ko'rsatadi).
"""

import base64
import importlib.util
import logging
import os
import re
import shutil
import tempfile

log = logging.getLogger(__name__)

# http.cookiejar faylning BIRINCHI qatorida shu sarlavhani talab qiladi, aks
# holda butun faylni rad etadi (LoadError).
_NETSCAPE_MAGIC_RE = re.compile(r"#( Netscape)? HTTP Cookie File")
_NETSCAPE_MAGIC = "# Netscape HTTP Cookie File"

# Login qilinganini bildiruvchi cookie'lar — bittasi ham bo'lmasa bot-tekshiruvi
# o'tmaydi.
_AUTH_COOKIES = ("SID", "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO")

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


def _normalize_cookies(content: str) -> tuple[str, int]:
    """Env orqali kelgan cookies.txt'ni yt-dlp o'qiy oladigan holga keltiradi.

    Ikki tuzoq: (1) Netscape formati TAB bilan ajratiladi, Railway kabi env
    maydonlari tab'ni bo'sh joyga aylantiradi va yt-dlp BARCHA qatorlarni
    jimgina o'tkazib yuboradi (0 ta cookie → "not a bot"); (2) sarlavha qatori
    bo'lmasa http.cookiejar butun faylni rad etadi.
    """
    out: list[str] = []
    repaired = 0
    for line in content.splitlines():
        stripped = line.strip()
        is_cookie = stripped and (
            not stripped.startswith("#") or stripped.startswith("#HttpOnly_")
        )
        if not is_cookie or "\t" in line:
            out.append(line)
            continue
        # maxsplit=6 → oxirgi maydon (qiymat) ichidagi bo'sh joylar saqlanadi.
        parts = line.split(None, 6)
        if len(parts) == 7:
            out.append("\t".join(parts))
            repaired += 1
        else:
            out.append(line)

    content = "\n".join(out) + "\n"
    # Sarlavhasiz (faqat cookie qatorlari qo'yilgan) fayl butunlay rad etiladi.
    first = next((ln for ln in out if ln.strip()), "")
    if not _NETSCAPE_MAGIC_RE.match(first):
        content = _NETSCAPE_MAGIC + "\n" + content
        log.info("Cookie matnida Netscape sarlavhasi yo'q edi — qo'shildi")
    return content, repaired


def _check_cookies(path: str) -> None:
    """Cookie fayl haqiqatan o'qilyaptimi — sonini va login cookie'sini loglaydi."""
    try:
        from yt_dlp.cookies import YoutubeDLCookieJar

        jar = YoutubeDLCookieJar(path)
        jar.load(ignore_discard=True, ignore_expires=True)
        names = {c.name for c in jar}
    except Exception as e:
        log.error("Cookie faylni o'qib bo'lmadi (%s) — cookie'siz davom etamiz", e)
        return
    if not names:
        log.error(
            "Cookie fayl BUZUQ — 0 ta cookie o'qildi. Sabab odatda: env qiymatida "
            "TAB'lar yo'qolgan. YT_COOKIES_B64 (base64) ishlating."
        )
        return
    found = [n for n in _AUTH_COOKIES if n in names]
    if found:
        log.info(
            "YouTube cookie'lari yuklandi: %d ta (login: %s)", len(names), ", ".join(found)
        )
    else:
        log.warning(
            "YouTube cookie'lari yuklandi (%d ta), lekin login cookie'si (%s) YO'Q — "
            "bot-tekshiruvi o'tmaydi. Login qilingan holda qayta eksport qiling.",
            len(names), "/".join(_AUTH_COOKIES),
        )


def _cookie_file() -> str | None:
    """Cookie faylini bir marta tayyorlaydi (fayl, base64 yoki xom env matnidan)."""
    global _COOKIE_FILE, _COOKIE_LOADED
    if _COOKIE_LOADED:
        return _COOKIE_FILE
    _COOKIE_LOADED = True

    path = os.getenv("YT_COOKIES_FILE", "").strip()
    if path:
        if os.path.isfile(path):
            _COOKIE_FILE = path
            log.info("YouTube cookie fayli: %s", path)
            _check_cookies(path)
        else:
            log.warning("YT_COOKIES_FILE topilmadi: %s", path)
        return _COOKIE_FILE

    # Base64 — env orqali uzatishning ISHONCHLI yo'li: tab/qator buzilmaydi.
    b64 = os.getenv("YT_COOKIES_B64", "").strip()
    if b64:
        try:
            content = base64.b64decode(b64, validate=True).decode("utf-8")
        except Exception as e:
            log.error("YT_COOKIES_B64 dekod qilinmadi (%s) — cookie ishlatilmaydi", e)
            return None
    else:
        content = os.getenv("YT_COOKIES", "")

    if not content.strip():
        return None

    content, repaired = _normalize_cookies(content)
    if repaired:
        log.warning(
            "Cookie'ning %d qatorida TAB yo'q edi (env qiymati buzilgan) — tiklandi. "
            "Ishonchliroq: YT_COOKIES_B64 ishlating.",
            repaired,
        )

    fd, tmp = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    _COOKIE_FILE = tmp
    log.info("YouTube cookie'lari env'dan yozildi (%s)", tmp)
    _check_cookies(tmp)
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
