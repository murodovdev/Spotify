import html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot import keyboards, texts
from bot.db import repo

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    connected = await repo.is_connected(message.from_user.id)
    await message.answer(
        texts.WELCOME.format(name=html.escape(message.from_user.first_name or "do'st")),
        reply_markup=keyboards.main_menu(connected),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP)


@router.callback_query(F.data == "menu:help")
async def cb_help(cq: CallbackQuery) -> None:
    await cq.answer()
    await cq.message.answer(texts.HELP)


@router.callback_query(F.data == "noop")
async def cb_noop(cq: CallbackQuery) -> None:
    await cq.answer()
