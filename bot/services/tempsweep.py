"""Orphan temp fayllarni tozalash — crash/interrupt'dan keyin disk to'lmasin.

Normal holatda handlerlar `tempfile.TemporaryDirectory` (context manager) bilan
o'zini tozalaydi. Ammo jarayon o'ldirilsa (Railway restart, OOM, deploy) yarim
yuklangan papkalar qolishi mumkin. Bu modul ularni startupda va davriy ravishda
supurib tashlaydi.

Temp `/tmp` (ephemeral konteyner diski)da — /data volume'да EMAS, shu sabab bu
yerni supurish persistent ma'lumotga tegmaydi.
"""

import logging
import os
import shutil
import tempfile
import time

log = logging.getLogger(__name__)

# Loyihaning barcha TemporaryDirectory prefikslari (downloader, handlers, video).
# `yt_cookies_` ATAYIN yo'q — cookie fayli faol, supurilmasligi kerak.
_PREFIXES = ("spdl_", "ytdl_", "vidl_", "vidrecog_", "recog_")

# Shundan eski orphanlar o'chiriladi. Bitta yuklab olish hech qachon bunchalik
# cho'zilmaydi, shu sabab faol ishni o'chirib yuborish xavfi yo'q.
STALE_SECONDS = 3600


def temp_root() -> str:
    return tempfile.gettempdir()


def sweep(max_age: float = STALE_SECONDS) -> int:
    """Prefiksga mos, max_age dan eski orphan temp papka/fayllarni o'chiradi."""
    root = temp_root()
    now = time.time()
    removed = 0
    try:
        entries = os.listdir(root)
    except OSError:
        return 0
    for name in entries:
        if not name.startswith(_PREFIXES):
            continue
        path = os.path.join(root, name)
        try:
            if now - os.path.getmtime(path) < max_age:
                continue  # yaqinda o'zgargan — hali faol bo'lishi mumkin
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed


def disk_free_mb() -> float:
    try:
        return shutil.disk_usage(temp_root()).free / (1024 * 1024)
    except OSError:
        return -1.0
