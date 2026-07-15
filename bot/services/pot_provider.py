"""bgutil PO token provider serverini boshqarish.

YouTube datacenter IP'larni bot deb bloklaydi ("Sign in to confirm you're
not a bot"). bgutil-ytdlp-pot-provider Google BotGuard'ni Deno ichida ishlatib
har so'rovga yangi PO token yaratadi. Ikki qism birga ishlaydi:

* pip plagini (`bgutil-ytdlp-pot-provider`) — yt-dlp uni avtomatik topadi va
  http://127.0.0.1:4416 dagi serverdan token so'raydi;
* HTTP server (bu modul ishga tushiradi) — Dockerfile'da /opt/bgutil ga
  o'rnatilgan, Deno bilan ishlaydi.

Server topilmasa (lokal dev muhit) — jim o'tkazib yuboriladi: plugin token
ololmasa yt-dlp tokensiz davom etadi, bot ishlashdan to'xtamaydi.
"""

import logging
import os
import subprocess

log = logging.getLogger(__name__)

_SERVER_DIR = "/opt/bgutil/server"
_proc: subprocess.Popen | None = None


def start() -> None:
    """PO token serverini background jarayon sifatida ishga tushiradi."""
    global _proc
    modules_dir = os.path.join(_SERVER_DIR, "node_modules")
    if not os.path.isdir(modules_dir):
        log.info("bgutil PO token serveri o'rnatilmagan — tokensiz davom etamiz")
        return
    try:
        # README bo'yicha Deno rejimi node_modules ichidan ishga tushiriladi.
        _proc = subprocess.Popen(
            [
                "deno", "run",
                "--allow-env", "--allow-net",
                "--allow-ffi=.", "--allow-read=.",
                "../src/main.ts",
            ],
            cwd=modules_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("bgutil PO token serveri ishga tushdi (port 4416, pid %d)", _proc.pid)
    except Exception:
        log.exception("bgutil PO token serverini ishga tushirib bo'lmadi")
        _proc = None


def stop() -> None:
    global _proc
    if _proc is not None:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _proc.kill()
        _proc = None
