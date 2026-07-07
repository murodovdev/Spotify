"""Admin kirish nazorati — aiogram filtri va ruxsat yordamchilari."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.admin import repo, roles
from bot.admin.roles import Perm


class AdminFilter(BaseFilter):
    """Faqat adminlar uchun. Handlerга `role` ni inject qiladi."""

    async def __call__(self, event: TelegramObject) -> bool | dict:
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        role = await repo.get_role(user.id)
        if role is None:
            return False
        return {"role": role}


async def ensure_perm(event: CallbackQuery | Message, role: str, perm: Perm) -> bool:
    """Ruxsat bo'lmasa foydalanuvchiни ogohlantiradi va False qaytaradi."""
    if roles.has_perm(role, perm):
        return True
    text = "⛔ You don't have permission for this action."
    if isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
    else:
        await event.answer(text)
    return False
