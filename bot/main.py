import asyncio
import logging
import os

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiohttp import web

from bot.config import settings
from bot.db import repo
from bot.db.database import close_db, init_db
from bot.handlers import library, links, search, settings as settings_handlers, start
from bot.services.spotify import spotify
from bot.web.oauth import build_app

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="🏠 Asosiy menyu"),
    BotCommand(command="liked", description="❤️ Liked Songs yuklab olish"),
    BotCommand(command="settings", description="⚙️ Sifat sozlamalari"),
    BotCommand(command="history", description="📜 Oxirgi yuklab olinganlar"),
    BotCommand(command="help", description="ℹ️ Qo'llanma"),
]


class UserMiddleware(BaseMiddleware):
    """Har bir murojaatda foydalanuvchini bazada ro'yxatga oladi."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user:
            await repo.upsert_user(user.id, user.username, user.first_name)
        return await handler(event, data)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    await init_db(settings.db_path)

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.include_routers(
        start.router,
        library.router,
        settings_handlers.router,
        links.router,
        search.router,  # catch-all matn qidiruv — oxirida turishi shart
    )

    # OAuth callback web-serveri (Railway shu portni tashqariga ochadi).
    # Port band bo'lsa bot baribir ishlayveradi — faqat Spotify ulash ishlamaydi.
    runner = web.AppRunner(build_app(bot))
    await runner.setup()
    try:
        host = "0.0.0.0" if os.getenv("RAILWAY_PUBLIC_DOMAIN") else "127.0.0.1"
        site = web.TCPSite(runner, host, settings.port)
        await site.start()
        log.info("OAuth server: %s:%s (redirect: %s)", host, settings.port, settings.redirect_uri)
    except OSError as e:
        log.warning("OAuth serverni %s portda ochib bo'lmadi (%s) — Spotify ulash o'chiq", settings.port, e)

    if not spotify.has_credentials:
        log.warning(
            "SPOTIFY_CLIENT_ID/SECRET kiritilmagan — bot embed rejimda ishlaydi "
            "(Liked Songs va Spotify ulash o'chiq bo'ladi)"
        )

    try:
        await bot.set_my_commands(COMMANDS)
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("Bot ishga tushdi (polling)")
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await spotify.close()
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        import uvloop
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
