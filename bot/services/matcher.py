"""YouTube'dan eng mos audioni topish (yt-dlp qidiruvi orqali).

ytmusicapi o'rniga yt-dlp ishlatiladi: YT Music'ning "songs" qidiruvi tez-tez
buzilib turadi, yt-dlp esa faol qo'llab-quvvatlanadi va natijalari sifatli.
"""

import asyncio
import logging
import re
from difflib import SequenceMatcher

from yt_dlp import YoutubeDL

from bot.services import ytdlp_common
from bot.services.spotify import Track

log = logging.getLogger(__name__)

# Shundan yuqori ball — ishonchsiz moslik, rad etiladi
MAX_SCORE = 30.0

# Maqsad trekda bo'lmasa, kandidat sarlavhasidagi bu so'zlar jarima oladi
BAD_WORDS = (
    "live", "instrumental", "karaoke", "cover", "remix", "slowed", "sped up",
    "speed up", "8d", "reverb", "reaction", "nightcore", "bass boosted", "loop",
    "1 hour", "10 hours", "mashup",
)

_SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "skip_download": True,
    "noplaylist": True,
    "socket_timeout": 15,
}


def _clean(s: str) -> str:
    return re.sub(r"[^\w\s]", " ", (s or "").lower()).strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _clean(a), _clean(b)).ratio()


def _yt_entries(query: str, limit: int) -> list[dict]:
    with YoutubeDL(ytdlp_common.apply(dict(_SEARCH_OPTS))) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    return list(info.get("entries") or [])


def _sc_entries(query: str, limit: int) -> list[dict]:
    # SoundCloud'da YouTube bot-detection muammosi yo'q, shu sabab ytdlp_common
    # (player_client/PO token/cookie) qo'llanmaydi — sof qidiruv opts yetarli.
    with YoutubeDL(dict(_SEARCH_OPTS)) as ydl:
        info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
    return list(info.get("entries") or [])


def _score(entry: dict, track: Track) -> float:
    duration = entry.get("duration") or 0
    dur_diff = abs(duration - track.duration) if duration and track.duration else 12.0

    cand_title = entry.get("title") or ""
    channel = entry.get("channel") or entry.get("uploader") or ""

    title_sim = max(
        _similarity(cand_title, track.title),
        _similarity(cand_title, f"{track.artists} {track.title}"),
    )
    artist_sim = max(
        _similarity(channel, track.artists),
        1.0 if _clean(track.artists) and _clean(track.artists) in _clean(cand_title) else 0.0,
    )

    penalty = 0.0
    cand_low = cand_title.lower()
    target_low = f"{track.title} {track.artists}".lower()
    for word in BAD_WORDS:
        if word in cand_low and word not in target_low:
            penalty += 10.0

    return dur_diff + (1 - title_sim) * 15 + (1 - artist_sim) * 10 + penalty


def _pick_sync(track: Track) -> str | None:
    query = f"{track.artists} {track.title}"
    try:
        entries = _yt_entries(query, 6)
    except Exception:
        log.exception("YouTube qidiruv xatosi: %s", query)
        return None

    candidates = [
        (_score(e, track), e["id"]) for e in entries if e.get("id")
    ]
    if not candidates:
        return None
    best_score, best_id = min(candidates)
    if best_score > MAX_SCORE:
        log.info("Mos audio topilmadi (ball %.1f): %s", best_score, query)
        return None
    return best_id


async def find_video_id(track: Track) -> str | None:
    return await asyncio.to_thread(_pick_sync, track)


# Fallbackда ketma-ket sinaladigan SoundCloud nomzodlar soni. Eng yaxshi natija
# DRM himoyalangan yoki o'chirilgan bo'lsa, keyingisi (masalan DRM'siz qayta-yuk)
# ishlashi mumkin.
_SC_CANDIDATES = 3


def _pick_sc_sync(track: Track) -> list[str]:
    query = f"{track.artists} {track.title}"
    try:
        entries = _sc_entries(query, 8)
    except Exception:
        log.exception("SoundCloud qidiruv xatosi: %s", query)
        return []

    # SoundCloud entry'da audio manzili sifatida permalink (webpage_url) ishlatiladi.
    candidates = sorted(
        (
            (_score(e, track), e.get("webpage_url") or e.get("url"))
            for e in entries
            if e.get("webpage_url") or e.get("url")
        ),
        key=lambda c: c[0],
    )
    urls = [url for score, url in candidates if score <= MAX_SCORE]
    if not urls:
        log.info("SoundCloud mos audio topilmadi: %s", query)
    return urls[:_SC_CANDIDATES]


async def find_soundcloud_urls(track: Track) -> list[str]:
    """YouTube yiqilганда fallback: SoundCloud'dan mos trek permalinklari (ballash
    tartibida). Ketma-ket sinash uchun bir nechta nomzod qaytaradi."""
    return await asyncio.to_thread(_pick_sc_sync, track)


def _strip_channel_prefix(title: str, channel: str) -> str:
    """"Artist - Song" ko'rinishidagi sarlavhadan kanal nomini olib tashlaydi."""
    m = re.match(rf"^\s*{re.escape(channel)}\s*[-–—:|]\s*(.+)$", title, re.I)
    return m.group(1).strip() if m else title


def _yt_search_sync(query: str, limit: int) -> list[Track]:
    try:
        entries = _yt_entries(query, limit)
    except Exception:
        log.exception("YouTube qidiruv xatosi: %s", query)
        return []
    tracks: list[Track] = []
    seen: set[str] = set()
    for e in entries:
        video_id = e.get("id")
        duration = int(e.get("duration") or 0)
        # Shorts va juda uzun videolarni tashlab yuboramiz
        if not video_id or video_id in seen or duration < 60 or duration > 5400:
            continue
        seen.add(video_id)
        channel = e.get("channel") or e.get("uploader") or ""
        title = _strip_channel_prefix(e.get("title") or "", channel)
        tracks.append(
            Track(
                id=f"yt:{video_id}",
                title=title,
                artists=channel,
                artist_id="",
                album="",
                album_id="",
                duration=duration,
                cover_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                thumb_url=f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                year="",
                track_no=0,
                video_id=video_id,
            )
        )
    return tracks


async def yt_search(query: str, limit: int = 12) -> list[Track]:
    """Embed rejimda matn qidiruv — to'g'ridan-to'g'ri YouTube'dan."""
    return await asyncio.to_thread(_yt_search_sync, query, min(limit, 15))
