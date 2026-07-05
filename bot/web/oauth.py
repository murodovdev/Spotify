"""Spotify OAuth callback uchun kichik aiohttp server."""

import logging

from aiogram import Bot
from aiohttp import web

from bot.db import repo
from bot.i18n import OAUTH_SUCCESS_PAGE, get_texts
from bot.security import parse_state
from bot.services.spotify import spotify

log = logging.getLogger(__name__)


def _page(icon: str, title: str, text: str, status: int = 200) -> web.Response:
    return web.Response(
        text=OAUTH_SUCCESS_PAGE.format(icon=icon, title=title, text=text),
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
            t = get_texts(None)
            return _page("😕", t.OAUTH_CANCEL_TITLE, t.OAUTH_CANCEL_TEXT, status=400)
        try:
            await spotify.exchange_code(code, user_id)
        except Exception:
            log.exception("OAuth code almashinuvida xato")
            t = get_texts(None)
            return _page("⚠️", t.OAUTH_ERROR_TITLE, t.OAUTH_ERROR_TEXT, status=500)

        lang = await repo.get_lang(user_id)
        t = get_texts(lang)
        try:
            await bot.send_message(user_id, t.CONNECTED_MSG)
        except Exception:
            pass
        return _page("✅", t.OAUTH_OK_TITLE, t.OAUTH_OK_TEXT)

    import time
    _start = time.monotonic()

    async def health(_: web.Request) -> web.Response:
        uptime = int(time.monotonic() - _start)
        return web.json_response({"status": "ok", "uptime_s": uptime})

    app = web.Application()
    app.router.add_get("/callback", callback)
    app.router.add_get("/health", health)
    app.router.add_get("/", health)
    return app
