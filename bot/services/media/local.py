"""Jarayon ichida ishlaydigan media backend — bugungi xatti-harakat.

Bu yerda hech qanday yangi mantiq yo'q: mavjud `downloader` va `video_dl`
funksiyalariga yupqa adapter. Shu sabab Phase 0 xatti-harakatni umuman
o'zgartirmaydi va istalgan vaqtda `MEDIA_BACKEND=local` bilan qaytish mumkin.
"""

from bot.services import downloader, video_dl
from bot.services.downloader import Downloaded
from bot.services.media.base import MediaBackend
from bot.services.spotify import Track
from bot.services.video_dl import VideoInfo


class LocalBackend(MediaBackend):
    name = "local"

    async def download_track(self, track: Track, bitrate: str, tmpdir: str) -> Downloaded:
        return await downloader.download(track, bitrate, tmpdir)

    async def download_yt_audio(self, video_id: str, fmt: str, tmpdir: str) -> str:
        return await video_dl.download_yt_audio(video_id, fmt, tmpdir)

    async def download_video(self, url: str, platform: str, tmpdir: str) -> VideoInfo:
        return await video_dl.download_video(url, platform, tmpdir)

    async def extract_audio(self, url: str, tmpdir: str) -> str:
        return await video_dl.download_audio(url, tmpdir)
