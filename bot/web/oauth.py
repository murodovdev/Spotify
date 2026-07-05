"""Spotify OAuth callback uchun kichik aiohttp server."""

import logging

from aiogram import Bot
from aiohttp import web

from bot import texts
from bot.security import parse_state
from bot.services.spotify import spotify

log = logging.getLogger(__name__)


def _page(icon: str, title: str, text: str, status: int = 200) -> web.Response:
    return web.Response(
        text=texts.OAUTH_SUCCESS_PAGE.format(icon=icon, title=title, text=text),
        content_type="text/html",
        status=status,
    )


def build_app(bot: Bot) -> web.Application:
    async def callback(request: web.Request) -> web.Response:
        error = request.query.get("error")
        code = request.query.get("code")
        state = request.query.get("state", "")
        user_id = parse_state(state)

        if error or not code or user_id is None:
            return _page(
                "😕",
                "Ulanish bekor qilindi",
                "Telegram'ga qaytib, qaytadan urinib ko'ring.",
                status=400,
            )
        try:
            await spotify.exchange_code(code, user_id)
        except Exception:
            log.exception("OAuth code almashinuvida xato")
            return _page(
                "⚠️",
                "Xatolik yuz berdi",
                "Telegram'ga qaytib, qaytadan urinib ko'ring.",
                status=500,
            )
        try:
            await bot.send_message(user_id, texts.CONNECTED_MSG)
        except Exception:
            pass
        return _page(
            "✅",
            "Spotify ulandi!",
            "Endi Telegram'ga qaytishingiz mumkin — bot tayyor.",
        )

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/callback", callback)
    app.router.add_get("/", health)
    return app
