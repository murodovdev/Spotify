import html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot import keyboards
from bot.admin import settings_store
from bot.db import repo
from bot.i18n import LANG_LABELS, WELCOME_BANNER, Texts, get_texts


router = Router(name="start")


def _welcome(t: Texts, first_name: str | None) -> str:
    name = html.escape((first_name or "").strip()) or "🎧"
    override = settings_store.get("welcome_override")
    # Admin override'ni HTML sifatida ESCAPE qilamiz: noto'g'ri HTML (masalan
    # "I <3 music" yoki yopilmagan teg) aks holda parse_mode=HTML'да /start'ни
    # HAR bir foydalanuvchi uchun buzardi. {name} placeholder escape'дан omon
    # qoladi; t.WELCOME esa bizники — ishonchli, escapelanmaydi.
    template = html.escape(override) if override else t.WELCOME
    try:
        text = template.format(name=name)
    except (KeyError, IndexError, ValueError):
        text = template  # admin matni format placeholderсиз bo'lishi mumkin
    announcement = settings_store.get("announcement")
    if announcement:
        text = f"{text}\n\n📣 {html.escape(announcement)}"
    return text


@router.message(CommandStart())
async def cmd_start(message: Message, lang: str | None, t: Texts) -> None:
    # Birinchi marta — til hali tanlanmagan: neytral banner ko'rsatamiz.
    if lang is None:
        await message.answer(WELCOME_BANNER, reply_markup=keyboards.lang_picker())
        return
    connected = await repo.is_connected(message.from_user.id)
    await message.answer(
        _welcome(t, message.from_user.first_name),
        reply_markup=keyboards.main_menu(connected, t),
    )


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(cq: CallbackQuery) -> None:
    lang = cq.data.split(":")[1]
    if lang not in LANG_LABELS:
        await cq.answer()
        return
    await repo.set_lang(cq.from_user.id, lang)
    t = get_texts(lang)
    await cq.answer(t.LANG_SET)
    connected = await repo.is_connected(cq.from_user.id)
    text = _welcome(t, cq.from_user.first_name)
    try:
        await cq.message.edit_text(text, reply_markup=keyboards.main_menu(connected, t))
    except Exception:
        await cq.message.answer(text, reply_markup=keyboards.main_menu(connected, t))


@router.message(Command("help"))
async def cmd_help(message: Message, t: Texts) -> None:
    await message.answer(t.HELP)


@router.callback_query(F.data == "menu:home")
async def cb_home(cq: CallbackQuery, t: Texts) -> None:
    """Sozlamalar yoki boshqa ekrandan asosiy menyuga qaytish."""
    await cq.answer()
    connected = await repo.is_connected(cq.from_user.id)
    text = _welcome(t, cq.from_user.first_name)
    try:
        await cq.message.edit_text(text, reply_markup=keyboards.main_menu(connected, t))
    except Exception:
        await cq.message.answer(text, reply_markup=keyboards.main_menu(connected, t))


@router.callback_query(F.data == "menu:help")
async def cb_help(cq: CallbackQuery, t: Texts) -> None:
    await cq.answer()
    await cq.message.answer(t.HELP)


@router.callback_query(F.data == "noop")
async def cb_noop(cq: CallbackQuery) -> None:
    await cq.answer()
