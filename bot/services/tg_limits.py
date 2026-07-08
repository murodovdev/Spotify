"""Telegram fayl hajmi chegaralari — yagona manba.

Chegaralar bot qaysi API serverga ulanganiga bog'liq, faylning o'ziga emas:

* **cloud** (api.telegram.org) — yuborish 50 MB, `getFile` orqali olish 20 MB.
* **local** (Local Bot API Server, `--local`) — yuborish 2 GB, olish cheklanmagan.

Rejim butun bot uchun bitta: token bir vaqtda ikkala serverda ishlay olmaydi
(lokal serverga o'tishdan oldin bulutda `logOut` chaqirish shart). Shu sabab
"fayl katta bo'lsa lokalga o'tamiz" degan runtime almashtirish mumkin emas —
rejim `TELEGRAM_API_MODE` bilan deploy vaqtida tanlanadi.

Chegaralar funksiya sifatida beriladi (konstanta emas): import vaqtida emas,
chaqiruv vaqtida o'qiladi, shunda testlarda va rejim o'zgarganda to'g'ri qiymat
chiqadi.

Bu modul `bot/services/media/` paketidan tashqarida: `downloader` uni import
qiladi, `media` paketi esa `downloader`ni — paket ichida bo'lsa import sikli
hosil bo'lardi.
"""

from bot.config import settings

# Bulutli API: yuborish chegarasi 50 MB. Zaxira qoldiramiz — multipart qo'shimcha
# baytlari va teg/muqova qo'shilishi hisobiga chegarani kesib o'tmaslik uchun.
_CLOUD_UPLOAD = 49 * 1024 * 1024
_CLOUD_DOWNLOAD = 20 * 1024 * 1024

# Local Bot API Server: 2000 MB (2 GB) yuborish. Olish amalda disk bilan cheklangan.
_LOCAL_UPLOAD = 2000 * 1024 * 1024
_LOCAL_DOWNLOAD = _LOCAL_UPLOAD


def is_local_api() -> bool:
    return (settings.telegram_api_mode or "cloud").strip().lower() == "local"


def max_upload_bytes() -> int:
    """Telegram'ga yuborish mumkin bo'lgan eng katta fayl."""
    return _LOCAL_UPLOAD if is_local_api() else _CLOUD_UPLOAD


def max_download_bytes() -> int:
    """`getFile` + `download_file` orqali qaytarib olish mumkin bo'lgan eng katta fayl."""
    return _LOCAL_DOWNLOAD if is_local_api() else _CLOUD_DOWNLOAD


def human_mb(size: int) -> str:
    return f"{size / 1_048_576:.0f} MB"
