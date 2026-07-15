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
import threading
import urllib.request

log = logging.getLogger(__name__)

_SERVER_DIR = "/opt/bgutil/server"
_PING_URL = "http://127.0.0.1:4416/ping"
_proc: subprocess.Popen | None = None


def _pump_output(proc: subprocess.Popen) -> None:
    """Server outputini bot logiga oqizadi — crash sabablari ko'rinsin."""
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            log.info("bgutil: %s", line)
    code = proc.wait()
    if code not in (0, None):
        log.warning("bgutil PO token serveri to'xtadi (exit code %s)", code)


def _health_check() -> None:
    """5 soniyadan keyin /ping — server haqiqatan javob beryaptimi."""
    try:
        with urllib.request.urlopen(_PING_URL, timeout=10) as resp:
            body = resp.read(200).decode("utf-8", "replace")
            log.info("bgutil ping OK: %s", body)
    except Exception as e:
        log.warning("bgutil ping ishlamadi (%s) — PO token olinmaydi", e)


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
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log.info("bgutil PO token serveri ishga tushdi (port 4416, pid %d)", _proc.pid)
        threading.Thread(target=_pump_output, args=(_proc,), daemon=True).start()
        threading.Timer(5.0, _health_check).start()
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
