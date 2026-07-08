"""Media backend tanlash — `MEDIA_BACKEND` env orqali (`local` | `remote`).

Chaqiruvchilar `media.backend()` orqali yagona nusxani oladi va faqat
`MediaBackend` shartnomasiga tayanadi:

    from bot.services import media

    res = await media.backend().download_track(track, bitrate, tmpdir)
"""

import logging
from functools import lru_cache

from bot.config import settings
from bot.services.media.base import MediaBackend, MediaUnavailable
from bot.services.media.local import LocalBackend

log = logging.getLogger(__name__)

__all__ = ["MediaBackend", "MediaUnavailable", "backend"]


@lru_cache(maxsize=1)
def backend() -> MediaBackend:
    kind = (settings.media_backend or "local").strip().lower()
    if kind == "remote":
        from bot.services.media.remote import RemoteBackend

        log.info("Media backend: remote (%s)", settings.media_server_url)
        return RemoteBackend(settings.media_server_url, settings.media_server_secret)
    if kind != "local":
        raise ValueError(f"Noma'lum MEDIA_BACKEND: {kind!r} (local | remote)")
    log.info("Media backend: local (in-process yt-dlp + ffmpeg)")
    return LocalBackend()
