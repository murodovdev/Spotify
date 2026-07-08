"""VPS media serveriga murojaat qiladigan backend — hali amalga oshirilmagan.

Bu fayl Phase 1 uchun shartnoma joyini band qilib turadi. Qasddan ishlamaydi:
konstruktor darhol `NotImplementedError` beradi, shunda `MEDIA_BACKEND=remote`
bo'lsa bot ishga tushishda yiqiladi — birinchi yuklab olishda emas. Yarim
ishlaydigan backend jim turishidan ko'ra baland ovozda yiqilgani yaxshi.

Rejalashtirilgan protokol (Phase 1 da to'ldiriladi):

    POST {MEDIA_SERVER_URL}/jobs
    X-TrackFlow-Timestamp: <unix seconds>
    X-TrackFlow-Nonce: <random hex>
    X-TrackFlow-Signature: hex(hmac_sha256(secret, timestamp.nonce.body))

    body: {"kind": "track|yt_audio|video|extract_audio", ...}

Server javobi ish natijasini (fayl yoki Telegram `file_id`) qaytaradi.
Imzo timestamp + nonce ustidan hisoblanadi — replay hujumiga qarshi; server
eskirgan timestamp'ni (masalan 60 soniyadan katta farq) rad etadi.

`file_id` haqida ogohlantirish: agar media server faylni Local Bot API Server
orqali yuborsa, qaytgan `file_id` bulutli API'da ishlamaydi. `track_cache`
aynan `file_id` bo'yicha kalitlanadi, shuning uchun Phase 3 da yo bot ham
o'sha lokal API'ga ulanishi, yoki kesh backend bo'yicha kalitlanishi shart.
"""

from bot.services.downloader import Downloaded
from bot.services.media.base import MediaBackend, MediaUnavailable
from bot.services.spotify import Track
from bot.services.video_dl import VideoInfo


class RemoteBackend(MediaBackend):
    name = "remote"

    def __init__(self, base_url: str, secret: str) -> None:
        raise NotImplementedError(
            "Remote media backend hali tayyor emas (Phase 1). "
            "MEDIA_BACKEND=local qo'ying."
        )

    async def download_track(self, track: Track, bitrate: str, tmpdir: str) -> Downloaded:
        raise MediaUnavailable("remote backend not implemented")

    async def download_yt_audio(self, video_id: str, fmt: str, tmpdir: str) -> str:
        raise MediaUnavailable("remote backend not implemented")

    async def download_video(self, url: str, platform: str, tmpdir: str) -> VideoInfo:
        raise MediaUnavailable("remote backend not implemented")

    async def extract_audio(self, url: str, tmpdir: str) -> str:
        raise MediaUnavailable("remote backend not implemented")
