"""Logs bo'limi uchun in-memory halqa bufer.

So'nggi WARNING/ERROR yozuvlarni xotirada ushlab turadi — server fayllariga
kirmasdan Telegram'дан ko'rish uchun. Kichik (bounded) — hech qachon o'smaydi.
"""

from __future__ import annotations

import logging
import time
from collections import deque

_MAX = 500


class _Rec:
    __slots__ = ("ts", "level", "logger", "msg")

    def __init__(self, ts: float, level: str, logger: str, msg: str):
        self.ts = ts
        self.level = level
        self.logger = logger
        self.msg = msg


_buffer: deque[_Rec] = deque(maxlen=_MAX)


class RingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        _buffer.append(_Rec(record.created, record.levelname, record.name, msg))


def install(level: int = logging.WARNING) -> None:
    """Root logger'ga halqa handlerни ulaydi (WARNING va yuqori)."""
    handler = RingHandler()
    handler.setLevel(level)
    logging.getLogger().addHandler(handler)


def query(level: str | None = None, keyword: str | None = None, limit: int = 500) -> list[_Rec]:
    kw = (keyword or "").lower()
    out = []
    for rec in reversed(_buffer):
        if level and rec.level != level:
            continue
        if kw and kw not in rec.msg.lower() and kw not in rec.logger.lower():
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def counts() -> dict[str, int]:
    c = {"ERROR": 0, "WARNING": 0, "CRITICAL": 0}
    for rec in _buffer:
        if rec.level in c:
            c[rec.level] += 1
    return c


def fmt_ts(ts: float) -> str:
    return time.strftime("%m-%d %H:%M:%S", time.localtime(ts))
