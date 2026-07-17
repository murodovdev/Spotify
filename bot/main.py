import asyncio
import logging
import os
import signal
import sys
import time

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, CallbackQuery, ErrorEvent, InlineQuery, Message
from aiohttp import web

from bot.admin import broadcast as admin_broadcast
from bot.admin import dashboard as admin_dashboard
from bot.admin import flows as admin_flows
from bot.admin import forcesub as admin_forcesub
from bot.admin import logbuf, settings_store
from bot.admin import repo as admin_repo
from bot.config import settings
from bot.db import maintenance, repo
from bot.db.database import close_db, init_db
from bot.handlers import (
    favorites,
    forcesub as forcesub_handler,
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
from bot.services import forcesub, pot_provider, tailscale_exit, tempsweep, tg_limits
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
    # Admin Logs bo'limi uchun so'nggi WARNING/ERROR yozuvlarini xotirada saqlaymiz.
    logbuf.install(logging.WARNING)


class UserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user:
            await repo.upsert_user(user.id, user.username, user.first_name)
            await repo.bump_active(user.id, time.time())
            lang = await repo.get_lang(user.id)
            data["lang"] = lang
            t = get_texts(lang)
            data["t"] = t

            # Rol (in-memory kesh — DB o'qishsiz). Adminlar ban va maintenance'дан
            # ozod: aks holda noto'g'ri/g'arazli ban egani botдан butunlay chiqarib
            # yuborardi va u o'zini panel orqali qutqara olmasди.
            role = await admin_repo.get_role(user.id)

            # Ban enforcement (arzon — in-memory kesh).
            blocked, reason = admin_repo.cached_block(user.id)
            if reason == "__expired__":
                await admin_repo.unban(user.id)  # muddati o'tган suspend
                blocked = False
            if blocked and role is None:
                await _notify_blocked(event, reason)
                return  # handlerни ishga tushirmaymiz

            # Maintenance rejimi — faqat adminlar o'tadi.
            if role is None and settings_store.is_maintenance():
                await _notify_maintenance(event)
                return

            # Majburiy obuna — adminlardan tashqari hamma uchun.
            if role is None and forcesub.enabled():
                if not await _force_sub_ok(event, user.id, t, data):
                    return
        return await handler(event, data)


async def _force_sub_ok(event, user_id: int, t, data) -> bool:
    """False qaytarsa handler ishga tushmaydi va obuna ekrani ko'rsatiladi."""
    # "✅ Qo'shildim" tugmasi gate'dan ozod — aks holda foydalanuvchi hech qachon
    # o'zini qayta tekshira olmasdi va botda qulflanib qolardi.
    if isinstance(event, CallbackQuery) and event.data == "fs:check":
        return True

    bot = data.get("bot")
    if bot is None:
        return True  # bot yo'q — tekshirib bo'lmaydi, ochiq qoldiramiz

    missing = await forcesub.missing_for(bot, user_id)
    if not missing:
        return True

    # Inline so'rov: ekran ko'rsatib bo'lmaydi — jim rad etamiz.
    if isinstance(event, InlineQuery):
        try:
            await event.answer([], cache_time=5, is_personal=True)
        except Exception:
            pass
        return False

    if isinstance(event, CallbackQuery):
        # Alert yetarli — har bosishда yangi xabar yubormaymiz (spam bo'lardi).
        await event.answer(t.FS_ALERT, show_alert=True)
        return False

    # Xabarlar uchun ekran ko'rsatamiz, lekin throttle bilan: foydalanuvchi
    # ketma-ket 5 ta xabar yozsa 5 ta bir xil ekran chiqmasin.
    if not forcesub.should_send_screen(user_id):
        return False
    try:
        await forcesub_handler.send_screen(bot, event.chat.id, t)
    except Exception:
        log.exception("Force-sub ekranini yuborib bo'lmadi: %s", user_id)
    return False


async def _notify_blocked(event, reason: str | None) -> None:
    text = "🚫 You are blocked from using this bot."
    if reason:
        text += f"\nReason: {reason}"
    try:
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(text)
    except Exception:
        pass


async def _notify_maintenance(event) -> None:
    text = settings_store.get("maintenance_msg")
    try:
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(text)
    except Exception:
        pass


def _build_session() -> AiohttpSession | None:
    """Bulutli API uchun None (aiogram sukut bo'yicha), lokal server uchun sessiya.

    Local Bot API Server 2 GB gacha yuborishga ruxsat beradi. Diqqat: tokenni
    lokal serverda ishlatishdan oldin bulutda `logOut` chaqirilishi kerak va
    eski bulutli `file_id`lar yaroqsiz bo'ladi (`track_cache` shular bo'yicha
    kalitlangan) — docs/HYBRID_MIGRATION.md ga qarang.
    """
    if not tg_limits.is_local_api():
        return None
    base = (settings.telegram_api_base or "").strip()
    if not base:
        raise RuntimeError(
            "TELEGRAM_API_MODE=local, lekin TELEGRAM_API_BASE berilmagan "
            "(masalan: http://127.0.0.1:8081)"
        )
    log.info("Telegram API: local server %s (yuborish %s gacha)",
             base, tg_limits.human_mb(tg_limits.max_upload_bytes()))
    return AiohttpSession(api=TelegramAPIServer.from_base(base, is_local=True))


async def main() -> None:
    _setup_logging()
    await init_db(settings.database_path)
    # Admin tizimi: sozlamalar keshi va ban keshini yuklaymiz.
    await settings_store.load()
    await admin_repo.load_bans()
    await admin_repo.load_admins()
    await forcesub.reload()  # majburiy obuna kanallari (xotira keshi)
    # Qayta ishga tushishдан oldin tugamagan broadcastlar 'failed' deb belgilanadi.
    stale = await admin_repo.reconcile_broadcasts()
    if stale:
        log.info("Reconcile: %d tugamagan broadcast 'failed' deb belgilandi", stale)
    # Oldingi ishga tushishdan qolgan orphan temp fayllarni tozalaymiz (crash/deploy).
    removed = tempsweep.sweep(max_age=0)
    if removed:
        log.info("Startup temp tozalash: %d orphan o'chirildi", removed)
    # Chiqish IP'ini uy internetiga ko'chiradi (cookie'siz bot-detection yechimi).
    # pot_provider'dan OLDIN: YTDLP_PROXY'ni shu qo'yadi. bgutil tokenlarni o'z
    # (Railway) IP'sidan yaratadi — PO token IP'ga emas, Visitor ID sessiyasiga
    # bog'lanadi, shu sabab bu mos kelmaslik muammo emas.
    tailscale_exit.start()
    # YouTube PO token serveri (bot-detection bypass) — mavjud bo'lsa.
    pot_provider.start()

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=_build_session(),
    )
    dp = Dispatcher()
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.inline_query.outer_middleware(UserMiddleware())  # localize the share caption

    @dp.errors()
    async def on_error(event: ErrorEvent):
        log.exception("Unhandled error: %s", event.exception)

    dp.include_routers(
        # Admin panel — oddiy handlerlardан oldin (FSM state handlerlari va /admin
        # ustuvor bo'lishi uchun; barcha admin handlerlari AdminFilter bilan himoyalangan).
        admin_dashboard.router,
        admin_flows.router,
        admin_broadcast.router,
        admin_forcesub.router,
        start.router,
        forcesub_handler.router,   # fs:check — gate'dan ozod
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
        pot_provider.stop()
        tailscale_exit.stop()
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
