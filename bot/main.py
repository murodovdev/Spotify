import asyncio
import logging
import os
import signal
import sys

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent
from aiohttp import web

from bot.config import settings
from bot.db import maintenance, repo
from bot.db.database import close_db, init_db
from bot.handlers import (
    favorites,
    library,
    links,
    playlist,
    post_download,
    recognize,
    search,
    settings as settings_handlers,
    start,
    video,
    youtube,
)
from bot.i18n import get_texts
from bot.services import tempsweep
from bot.services.spotify import spotify
from bot.web.oauth import build_app

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Menu"),
    BotCommand(command="liked", description="Liked Songs"),
    BotCommand(command="favorites", description="⭐ Favorites"),
    BotCommand(command="settings", description="Settings"),
    BotCommand(command="help", description="Help"),
]


def _setup_logging() -> None:
    is_railway = bool(os.getenv("RAILWAY_PUBLIC_DOMAIN"))
    if is_railway:
        fmt = '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
    else:
        fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, stream=sys.stdout)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


class UserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user:
            await repo.upsert_user(user.id, user.username, user.first_name)
            lang = await repo.get_lang(user.id)
            data["lang"] = lang
            data["t"] = get_texts(lang)
        return await handler(event, data)


async def main() -> None:
    _setup_logging()
    await init_db(settings.database_path)
    # Oldingi ishga tushishdan qolgan orphan temp fayllarni tozalaymiz (crash/deploy).
    removed = tempsweep.sweep(max_age=0)
    if removed:
        log.info("Startup temp tozalash: %d orphan o'chirildi", removed)

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.inline_query.outer_middleware(UserMiddleware())  # localize the share caption

    @dp.errors()
    async def on_error(event: ErrorEvent):
        log.exception("Unhandled error: %s", event.exception)

    dp.include_routers(
        start.router,
        library.router,
        favorites.router,
        settings_handlers.router,
        links.router,
        playlist.router,
        post_download.router,  # before search.router — FSM state handlers take priority
        recognize.router,      # media messages (audio/voice/video/video_note) → recognition
        youtube.router,        # YouTube links → audio extraction
        video.router,          # social media video links → download + Find Music
        search.router,
    )

    runner = web.AppRunner(build_app(bot))
    await runner.setup()
    try:
        # RAILWAY_ENVIRONMENT har doim Railway da set bo'ladi (public domain bo'lmasa ham).
        host = "0.0.0.0" if os.getenv("RAILWAY_ENVIRONMENT") else "127.0.0.1"
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

    shutdown_event = asyncio.Event()

    def _signal_handler():
        log.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _signal_handler)

    try:
        await bot.set_my_commands(COMMANDS)
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("Bot ishga tushdi (polling)")
        polling_task = asyncio.create_task(dp.start_polling(bot))
        maintenance_task = asyncio.create_task(maintenance.loop())
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        done, _ = await asyncio.wait(
            [polling_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
        )
        if shutdown_task in done:
            await dp.stop_polling()
            polling_task.cancel()
        maintenance_task.cancel()
    finally:
        log.info("Shutting down…")
        await runner.cleanup()
        await spotify.close()
        await repo.flush()
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        import uvloop
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
