"""yt-dlp uchun umumiy sozlamalar: cookie fayli va player_client fallback.

YouTube Railway kabi data-markaz IP'larini "bot" deb bloklaydi
("Sign in to confirm you're not a bot") va yosh-cheklovli videolarni rad etadi
("Sign in to confirm your age"). Ikkalasini ham hal qiladigan yagona ishonchli
yo'l — logindan olingan cookies.txt. Cookie env orqali beriladi:

  YOUTUBE_COOKIES       — cookies.txt matni (to'g'ridan-to'g'ri)
  YOUTUBE_COOKIES_B64   — base64 bilan kodlangan cookies.txt (ko'p qatorli
                          qiymatni Railway env'ga solish qulayroq)
  YOUTUBE_COOKIES_FILE  — mavjud cookies.txt fayl yo'li (masalan volume ichida)

Cookie berilmasa ham bot ishlaydi, lekin data-markaz IP'sida ko'p videolar
"bot" tekshiruviga tushishi mumkin.
"""

import base64
import logging
import os
import tempfile

log = logging.getLogger(__name__)

# Klient tanlash format ro'yxatiga ta'sir qiladi. `web`/`mweb` PO token talab
# qiladi va token'siz formatlarni "mavjud emas" deb belgilaydi ("Requested
# format is not available"). `web_safari` cookie bilan to'liq format beradi va
# yosh-cheklovini ochadi; `android`/`tv` — zaxira, ular ham progressiv format
# beradi. Cookie "bot" tekshiruvini hал qiladi, shuning uchun cookie bo'lsa
# bloklanadigan klientlarни ham ishlatsa bo'ladi.
_CLIENTS_WITH_COOKIES = ["web_safari", "android", "tv"]
_CLIENTS_NO_COOKIES = ["web_safari", "tv", "mweb"]

_cookie_path: str | None = None
_cookie_resolved = False


def _resolve_cookie_file() -> str | None:
    global _cookie_path, _cookie_resolved
    if _cookie_resolved:
        return _cookie_path
    _cookie_resolved = True

    path = os.getenv("YOUTUBE_COOKIES_FILE", "").strip()
    if path:
        if os.path.isfile(path):
            _cookie_path = path
            log.info("YouTube cookie fayli ishlatilmoqda: %s", path)
        else:
            log.warning("YOUTUBE_COOKIES_FILE topilmadi: %s", path)
        return _cookie_path

    content = os.getenv("YOUTUBE_COOKIES", "")
    b64 = os.getenv("YOUTUBE_COOKIES_B64", "").strip()
    if b64 and not content.strip():
        try:
            content = base64.b64decode(b64).decode("utf-8")
        except Exception:
            log.warning("YOUTUBE_COOKIES_B64 dekod qilinmadi — e'tiborsiz qoldirildi")
            content = ""

    if content.strip():
        fd, tmp = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        _cookie_path = tmp
        log.info("YouTube cookie env'dan vaqtinchalik faylga yozildi: %s", tmp)

    return _cookie_path


def has_cookies() -> bool:
    return _resolve_cookie_file() is not None


def apply(opts: dict) -> dict:
    """yt-dlp opts'ga cookie va player_client sozlamalarini qo'shadi (idempotent)."""
    cookie = _resolve_cookie_file()
    if cookie:
        opts.setdefault("cookiefile", cookie)
        clients = _CLIENTS_WITH_COOKIES
    else:
        clients = _CLIENTS_NO_COOKIES
    ea = opts.setdefault("extractor_args", {})
    ea.setdefault("youtube", {}).setdefault("player_client", list(clients))
    return opts
