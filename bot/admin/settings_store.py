"""bot_settings uchun keshli qatlam.

Har bir xabar/bosishда middleware maintenance & feature-flaglarni tekshiradi,
shu sabab qiymatlarni DB'дан emas, xotiradan o'qiymiz. Cache init_db'дан keyin
bir marta to'ldiriladi va yozuvда yangilanadi.
"""

from __future__ import annotations

from bot.db.database import db

# Sozlamalar sxemasi: key → (default, type, label, guruh)
# type: bool | int | str
DEFAULTS: dict[str, object] = {
    "maintenance": False,          # bot maintenance rejimida (faqat adminlar)
    "maintenance_msg": "🛠 The bot is under maintenance. Please try again later.",
    "feature_search": True,        # matn qidiruv yoqilgan
    "feature_recognize": True,     # musiqa tanish yoqilgan
    "feature_video": True,         # video yuklab olish yoqilgan
    "feature_similar": True,       # o'xshash qo'shiqlar yoqilgan
    "feature_effects": True,       # audio effektlar yoqilgan
    "force_sub": False,            # majburiy obuna yoqilgan (kanallar: force_subs jadvali)
    "download_limit": 0,           # har foydalanuvchiga kunlik limit (0 = cheksiz)
    "welcome_override": "",        # bo'sh bo'lmasa i18n WELCOME o'rniga
    "announcement": "",            # start'да ko'rsatiladigan e'lon (bo'sh = yo'q)
}

# Boolean sozlamalar (toggle UI uchun)
BOOL_KEYS = [k for k, v in DEFAULTS.items() if isinstance(v, bool)]

_cache: dict[str, str] = {}
_loaded = False


def _coerce(key: str, raw: str | None):
    default = DEFAULTS.get(key)
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw == "1"
    if isinstance(default, int):
        try:
            return int(raw)
        except ValueError:
            return default
    return raw


def _encode(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


async def load() -> None:
    """init_db'дан keyin bir marta chaqiriladi."""
    global _loaded
    cur = await db().execute("SELECT key, value FROM bot_settings")
    for row in await cur.fetchall():
        _cache[row["key"]] = row["value"]
    _loaded = True


def get(key: str):
    return _coerce(key, _cache.get(key))


async def set(key: str, value) -> None:
    raw = _encode(value)
    _cache[key] = raw
    await db().execute(
        """INSERT INTO bot_settings(key, value) VALUES(?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (key, raw),
    )
    await db().commit()


async def toggle(key: str) -> bool:
    # Faqat boolean sozlamalar — aks holda (masalan forged callback) int/str
    # qiymatni buzardik (download_limit 5 → 0).
    if key not in BOOL_KEYS:
        raise ValueError(f"{key!r} is not a boolean setting")
    new = not bool(get(key))
    await set(key, new)
    return new


def is_maintenance() -> bool:
    return bool(get("maintenance"))


def feature_enabled(name: str) -> bool:
    return bool(get(f"feature_{name}"))
