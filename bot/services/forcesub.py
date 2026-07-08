"""Majburiy obuna: a'zolikni tekshirish, keshlash va xato bilan ishlash.

Ikki daraja kesh, chunki tekshiruv **har bir xabar va bosishда** ishlaydi:

1. Kanallar ro'yxati — xotirada (`_chats`). Admin o'zgartirsa `reload()`.
2. To'liq obuna bo'lgan foydalanuvchilar — `_verified` (TTL). Telegram
   `getChatMember` ga har safar murojaat qilmaymiz.

Kesh faqat **ijobiy** natijani saqlaydi. Obuna bo'lmagan foydalanuvchi hech
qachon keshlanmaydi: u kanalga qo'shilgach darhol o'tishi kerak.

Xato siyosati — konfiguratsiya xatosida **ochiq qolamiz** (fail-open): bot
kanalda admin bo'lmasa yoki kanal o'chirilgan bo'lsa, `getChatMember` xato
beradi. Bunda foydalanuvchini bloklash butun botni ishlatib bo'lmas holga
keltiradi va admin ham panelga kira olmay qolishi mumkin. Shu sabab bunday
kanal tekshiruvdan chetlab o'tiladi va ERROR darajasida yoziladi.
Telegram aniq "left/kicked" degan javob bergandagina foydalanuvchi bloklanadi.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.admin import settings_store
from bot.db import forcesub_repo

log = logging.getLogger(__name__)

# Telegram a'zolik holatlari, obuna hisoblanadiganlari.
_OK_STATUSES = frozenset({"creator", "administrator", "member"})

# Ijobiy natija shu muddatga keshlanadi. Qisqa: foydalanuvchi kanaldan chiqsa
# bir necha daqiqada yana so'raladi. "✅ Qo'shildim" bosilsa kesh bekor qilinadi.
_TTL = 600.0
_MAX_VERIFIED = 50_000

_verified: "OrderedDict[int, float]" = OrderedDict()
_chats: list = []
_chats_loaded = False

# Tekshiruvi xato bergan (fail-open bo'lgan) chatlar: chat_id → oxirgi xato matni.
# Admin panelida ko'rsatiladi — aks holda majburiy obuna jimgina ishlamay turadi.
_broken: dict[int, str] = {}
_last_noop_warn = 0.0


def enabled() -> bool:
    return bool(settings_store.get("force_sub")) and bool(_chats)


async def reload() -> None:
    """Kanallar ro'yxatini DB'dan qayta o'qiydi va foydalanuvchi keshini tozalaydi."""
    global _chats, _chats_loaded
    _chats = list(await forcesub_repo.list_enabled())
    _chats_loaded = True
    _verified.clear()  # ro'yxat o'zgardi — eski "obuna" natijalari yaroqsiz
    _broken.clear()    # xato holati ham eskirdi (bot admin qilingan bo'lishi mumkin)
    log.info("Force-sub: %d ta faol kanal yuklandi", len(_chats))


def chats() -> list:
    return _chats


def invalidate(user_id: int) -> None:
    _verified.pop(user_id, None)


def _remember(user_id: int) -> None:
    _verified[user_id] = time.monotonic() + _TTL
    _verified.move_to_end(user_id)
    while len(_verified) > _MAX_VERIFIED:
        _verified.popitem(last=False)


def _cached_ok(user_id: int) -> bool:
    exp = _verified.get(user_id)
    if exp is None:
        return False
    if time.monotonic() >= exp:
        _verified.pop(user_id, None)
        return False
    return True


async def _is_member(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Bitta chat uchun a'zolik. Konfiguratsiya xatosida True (fail-open)."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except TelegramAPIError as e:
        # "chat not found", "bot is not a member", "not enough rights",
        # "member list is inaccessible" — bularning hammasi admin muammosi.
        _broken[chat_id] = str(e)[:120]
        log.error(
            "Force-sub: %s chatini tekshirib bo'lmadi (bot admin emasmi?): %s",
            chat_id, e,
        )
        return True
    _broken.pop(chat_id, None)
    status = getattr(member, "status", "")
    if status in _OK_STATUSES:
        return True
    # Cheklangan a'zo hamon guruh ichida bo'lishi mumkin.
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return False  # left | kicked


async def missing_for(bot: Bot, user_id: int) -> list:
    """Foydalanuvchi qo'shilmagan chatlar. Bo'sh ro'yxat = ruxsat berilsin."""
    if not enabled():
        return []
    if _cached_ok(user_id):
        return []

    missing = [c for c in _chats if not await _is_member(bot, c["chat_id"], user_id)]
    if not missing:
        _remember(user_id)
        _warn_if_noop()
    return missing


def _warn_if_noop() -> None:
    """Har bir chat fail-open bo'lsa, majburiy obuna amalda hech kimni to'smaydi.

    Bu holat jim o'tib ketmasin: admin "yoqilgan" deb o'ylab yuradi. Soatiga bir
    marta ogohlantiramiz (har o'tgan foydalanuvchida emas).
    """
    global _last_noop_warn
    if not _chats or len(_broken) < len(_chats):
        return
    now = time.monotonic()
    if now - _last_noop_warn < 3600:
        return
    _last_noop_warn = now
    log.error(
        "Force-sub YOQILGAN, lekin %d/%d chatning tekshiruvi xato bermoqda — "
        "hech kim to'silmayapti. Bot o'sha chatlarda admin ekanini tekshiring.",
        len(_broken), len(_chats),
    )


def broken() -> dict[int, str]:
    """Tekshiruvi xato bergan chatlar (admin paneli uchun)."""
    return dict(_broken)


async def verify(bot: Bot, user_id: int) -> list:
    """"✅ Qo'shildim" uchun: keshni chetlab o'tib, qaytadan tekshiradi.

    Tugma bosilishiga hech qachon ishonmaymiz — har safar Telegram'dan so'raymiz.
    """
    invalidate(user_id)
    return await missing_for(bot, user_id)


# Obuna ekrani shu oraliqda bir marta yuboriladi (foydalanuvchi ketma-ket
# xabar yozsa bir xil ekran takrorlanmasin).
_SCREEN_COOLDOWN = 20.0
_screen_sent: "OrderedDict[int, float]" = OrderedDict()


def should_send_screen(user_id: int) -> bool:
    now = time.monotonic()
    last = _screen_sent.get(user_id)
    if last is not None and now - last < _SCREEN_COOLDOWN:
        return False
    _screen_sent[user_id] = now
    _screen_sent.move_to_end(user_id)
    while len(_screen_sent) > _MAX_VERIFIED:
        _screen_sent.popitem(last=False)
    return True


def chat_url(row) -> str:
    """Chatga kirish havolasi: ochiq bo'lsa @username, aks holda taklif havolasi."""
    if row["username"]:
        return f"https://t.me/{row['username']}"
    return row["invite_link"] or ""
