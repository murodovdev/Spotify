"""Media qayta ishlash uchun backend interfeysi.

Bot mantiqini og'ir media ishlaridan ajratadigan yagona chegara. Hozircha
`LocalBackend` (jarayon ichida yt-dlp + ffmpeg) yagona amalga oshirilgan
variant; kelajakda `RemoteBackend` xuddi shu shartnomani VPS media serveri
orqali bajaradi va chaqiruvchi kod o'zgarmaydi.

Shartnoma qoidalari:

* Har bir metod chaqiruvchi bergan `tmpdir` ichiga yozadi va fayl yo'lini
  qaytaradi. Tozalash — chaqiruvchining `TemporaryDirectory` mas'uliyatida.
* Xatolar domen istisnolari bilan qaytadi (`TrackNotFound`, `TooLarge`,
  `YTError`, `YTTooLarge`) — chaqiruvchilar allaqachon shularni ushlaydi.
* Backend butunlay ishlamayotgan bo'lsa `MediaUnavailable` ko'tariladi.
  Bu yagona *yangi* istisno: faqat remote backend uchun ma'noga ega
  (VPS o'chgan/yetib bo'lmaydi) va grace-degradatsiya shu yerga ulanadi.
"""

from abc import ABC, abstractmethod

from bot.services.downloader import Downloaded
from bot.services.spotify import Track
from bot.services.video_dl import VideoInfo


class MediaUnavailable(Exception):
    """Media backend vaqtincha ishlamayapti (tarmoq, VPS o'chgan, timeout).

    `TrackNotFound`dan farqi: bu yerda trek aybdor emas — qayta urinish
    mantiqiy. Chaqiruvchi foydalanuvchiga "keyinroq urinib ko'ring" deyishi
    va ishni navbatga qo'yishi mumkin.
    """


class MediaBackend(ABC):
    """Og'ir media operatsiyalari. Amalga oshirish lokal yoki masofaviy."""

    @abstractmethod
    async def download_track(self, track: Track, bitrate: str, tmpdir: str) -> Downloaded:
        """Trekni YouTube'dan topib, MP3 ga aylantiradi va teglaydi."""

    @abstractmethod
    async def download_yt_audio(self, video_id: str, fmt: str, tmpdir: str) -> str:
        """YouTube videosidan tanlangan formatda audio (mp3/m4a/flac/opus)."""

    @abstractmethod
    async def download_video(self, url: str, platform: str, tmpdir: str) -> VideoInfo:
        """Ijtimoiy tarmoq videosini yuklaydi."""

    @abstractmethod
    async def extract_audio(self, url: str, tmpdir: str) -> str:
        """Videodan audio ajratadi (musiqa aniqlash uchun)."""
