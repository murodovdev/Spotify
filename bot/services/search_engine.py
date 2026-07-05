"""Ko'p manbali intellektual qidiruv dvigateli.

Bitta katalogga tayanmaydi: metadata bir nechta ochiq, qonuniy manbadan yig'iladi va
audio manbasi bilan solishtiriladi. Hech bir katalog barcha yozuvlarni saqlamaydi, shu
sabab natijalar birlashtirilib, ko'p bosqichli moslashtirish orqali aniqlik oshiriladi.

Manbalar
--------
* iTunes Search API — sarlavha, ijrochi, albom, yil, JANR, muqova (kalitsiz).
* Deezer API        — sarlavha, ijrochi, albom, davomiylik, MASHHURLIK (rank), muqova.
* YouTube (yt-dlp)  — kafolatlangan yuklab olinadigan audio (kam uchraydigan treklar uchun ham).

Bosqichlar
----------
1. Normalizatsiya + so'rov variantlari (tozalash, transliteratsiya).
2. Manbalarni parallel so'rash (kesh bilan, minimal tashqi murojaat).
3. Kandidatlarni birlashtirish va dedup (ijrochi + asosiy sarlavha bo'yicha).
4. Fuzzy o'xshashlik + mashhurlik + metadata sifati → ishonch bali.
5. Reyting; zaif bo'lsa progressiv qayta urinish (variantlar, transliteratsiya).
6. Track ro'yxati (eng ishonchli birinchi). "Topilmadi" — faqat oxirgi chora.
"""

import asyncio
import logging
import math
import re
import time
import unicodedata
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

import aiohttp

from bot.services import matcher
from bot.services.spotify import Track, spotify

log = logging.getLogger(__name__)

ITUNES_URL = "https://itunes.apple.com/search"
DEEZER_URL = "https://api.deezer.com/search"

_PER_PROVIDER = 8
RESULT_LIMIT = 18
STRONG_CONF = 62.0  # kuchli moslik chegarasi
_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)

_CACHE_TTL = 3600.0
_CACHE_MAX = 300
_provider_cache: dict[tuple[str, str], tuple[float, list]] = {}
_result_cache: dict[str, tuple[float, list["Track"]]] = {}

# Versiya belgilari — so'rovda bo'lmasa, jarima oladi (asl studiya versiyasi ustunroq).
VERSION_WORDS = (
    "remaster", "remastered", "deluxe", "live", "acoustic", "remix", "explicit",
    "clean", "instrumental", "radio edit", "extended", "demo", "mono", "session",
    "sped up", "slowed", "reverb", "karaoke", "cover",
)
_NOISE = re.compile(
    r"\b(official|video|audio|lyrics?|lyric|hd|hq|mv|full|visualizer|music\s*video)\b",
    re.I,
)
_BRACKETS = re.compile(r"[\(\[\{].*?[\)\]\}]")

# Kirill (ru/uz) → lotin translit. Ko'p manbalar lotincha so'rovni yaxshiroq tushunadi.
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",  # o'zbek kirill
}


@dataclass
class Candidate:
    title: str
    artist: str
    album: str = ""
    year: str = ""
    genre: str = ""
    duration: int = 0
    cover: str = ""
    thumb: str = ""
    popularity: float = 0.0  # 0..1 ga normallashtirilgan
    source: str = ""  # it | dz | yt
    ext_id: str = ""
    video_id: str = ""
    confidence: float = 0.0


# --- Matn normalizatsiyasi ---

def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def _norm(s: str) -> str:
    s = _nfkc(s).casefold()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> set[str]:
    return set(_norm(s).split())


def _base_title(title: str) -> str:
    """Qavs ichidagi versiya belgilarisiz asosiy sarlavha (dedup kaliti uchun)."""
    return _norm(_BRACKETS.sub(" ", title or ""))


def _has_cyrillic(s: str) -> bool:
    return any("Ѐ" <= c <= "ӿ" for c in s)


def _translit(s: str) -> str:
    return "".join(_CYRILLIC.get(c, _CYRILLIC.get(c.lower(), c)) for c in _nfkc(s))


def _clean_query(raw: str) -> str:
    q = _NOISE.sub(" ", _nfkc(raw))
    return re.sub(r"\s+", " ", q).strip()


def _variants(raw: str) -> list[str]:
    """Progressiv qayta urinish uchun tartiblangan, takrorlanmas so'rov variantlari."""
    out: list[str] = []

    def add(x: str) -> None:
        x = x.strip()
        if x and x.lower() not in (s.lower() for s in out):
            out.append(x)

    base = _nfkc(raw).strip()
    add(base)
    add(_clean_query(base))
    if _has_cyrillic(base):
        add(_translit(base))
        add(_clean_query(_translit(base)))
    return out[:4]


# --- O'xshashlik va ishonch bali ---

def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _token_set_ratio(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    sorted_ratio = _ratio(" ".join(sorted(ta)), " ".join(sorted(tb)))
    return max(jaccard, sorted_ratio)


def _similarity(query: str, cand: Candidate) -> float:
    queries = [_norm(query)]
    tq = _norm(_translit(query))
    if tq and tq != queries[0]:
        queries.append(tq)
    forms = (
        cand.title,
        f"{cand.artist} {cand.title}",
        f"{cand.title} {cand.artist}",
    )
    best = 0.0
    for q in queries:
        for form in forms:
            fn = _norm(form)
            best = max(best, 0.5 * _ratio(q, fn) + 0.5 * _token_set_ratio(q, fn))
    return best


def _version_tag(title: str) -> str:
    low = (title or "").lower()
    for word in VERSION_WORDS:
        if word in low:
            return word
    return ""


def _confidence(query: str, cand: Candidate) -> float:
    sim = _similarity(query, cand)
    completeness = sum(
        bool(x) for x in (cand.album, cand.year, cand.duration, cand.cover)
    ) / 4.0
    src_bonus = 5.0 if cand.source in ("it", "dz") else 0.0
    score = sim * 70 + cand.popularity * 15 + completeness * 10 + src_bonus
    tag = _version_tag(cand.title)
    if tag and tag not in _norm(query):
        score -= 8  # so'ralmagan versiya (live/remix/...) pastroq
    return max(0.0, min(100.0, score))


# --- Provayderlar (kesh bilan) ---

async def _cached(provider: str, query: str, factory) -> list[Candidate]:
    key = (provider, _norm(query))
    now = time.monotonic()
    hit = _provider_cache.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    try:
        result = await factory()
    except Exception:
        log.warning("%s qidiruv xatosi: %s", provider, query, exc_info=True)
        result = []
    _provider_cache[key] = (now, result)
    while len(_provider_cache) > _CACHE_MAX:
        _provider_cache.pop(next(iter(_provider_cache)))
    return result


async def _itunes(query: str) -> list[Candidate]:
    async def go() -> list[Candidate]:
        session = await spotify.session()
        params = {"term": query, "media": "music", "entity": "song", "limit": _PER_PROVIDER}
        async with session.get(ITUNES_URL, params=params, timeout=_HTTP_TIMEOUT) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)
        out: list[Candidate] = []
        results = data.get("results") or []
        for i, it in enumerate(results):
            art = it.get("artworkUrl100") or ""
            out.append(
                Candidate(
                    title=it.get("trackName") or "",
                    artist=it.get("artistName") or "",
                    album=it.get("collectionName") or "",
                    year=(it.get("releaseDate") or "")[:4],
                    genre=it.get("primaryGenreName") or "",
                    duration=round((it.get("trackTimeMillis") or 0) / 1000),
                    cover=art.replace("100x100", "600x600"),
                    thumb=art,
                    popularity=1.0 - i / _PER_PROVIDER,
                    source="it",
                    ext_id=str(it.get("trackId") or i),
                )
            )
        return out

    return await _cached("itunes", query, go)


async def _deezer(query: str) -> list[Candidate]:
    async def go() -> list[Candidate]:
        session = await spotify.session()
        params = {"q": query, "limit": _PER_PROVIDER}
        async with session.get(DEEZER_URL, params=params, timeout=_HTTP_TIMEOUT) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)
        out: list[Candidate] = []
        for it in data.get("data") or []:
            album = it.get("album") or {}
            artist = it.get("artist") or {}
            rank = it.get("rank") or 0
            out.append(
                Candidate(
                    title=it.get("title") or "",
                    artist=artist.get("name") or "",
                    album=album.get("title") or "",
                    duration=int(it.get("duration") or 0),
                    cover=album.get("cover_xl") or album.get("cover_big") or "",
                    thumb=album.get("cover_medium") or "",
                    popularity=min(1.0, math.log10(rank + 1) / 6.0),
                    source="dz",
                    ext_id=str(it.get("id") or ""),
                )
            )
        return out

    return await _cached("deezer", query, go)


async def _youtube(query: str) -> list[Candidate]:
    async def go() -> list[Candidate]:
        tracks = await matcher.yt_search(query, _PER_PROVIDER)
        return [
            Candidate(
                title=t.title,
                artist=t.artists,
                duration=t.duration,
                cover=t.cover_url,
                thumb=t.thumb_url,
                popularity=1.0 - i / _PER_PROVIDER,
                source="yt",
                ext_id=t.video_id,
                video_id=t.video_id,
            )
            for i, t in enumerate(tracks)
        ]

    return await _cached("youtube", query, go)


async def _gather(query: str, use_youtube: bool = True) -> list[Candidate]:
    tasks = [_itunes(query), _deezer(query)]
    if use_youtube:
        tasks.append(_youtube(query))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    cands: list[Candidate] = []
    for r in results:
        if isinstance(r, list):
            cands += r
    return cands


# --- Birlashtirish, reyting, konvertatsiya ---

def _merge(cands: list[Candidate]) -> list[Candidate]:
    """(ijrochi, asosiy sarlavha) bo'yicha dedup; eng ishonchlisini saqlab, bo'sh
    maydonlarni boshqa manbalardan to'ldiradi."""
    best: dict[tuple[str, str], Candidate] = {}
    for c in cands:
        key = (_norm(c.artist), _base_title(c.title))
        cur = best.get(key)
        if cur is None:
            best[key] = c
            continue
        keep, drop = (c, cur) if c.confidence > cur.confidence else (cur, c)
        keep.album = keep.album or drop.album
        keep.year = keep.year or drop.year
        keep.genre = keep.genre or drop.genre
        keep.duration = keep.duration or drop.duration
        keep.cover = keep.cover or drop.cover
        keep.thumb = keep.thumb or drop.thumb
        keep.video_id = keep.video_id or drop.video_id
        keep.popularity = max(keep.popularity, drop.popularity)
        best[key] = keep
    return list(best.values())


def _rank(query: str, cands: list[Candidate]) -> list[Candidate]:
    scored = [replace(c) for c in cands]  # keshdagi obyektlarni o'zgartirmaymiz
    for c in scored:
        c.confidence = _confidence(query, c)
    merged = _merge(scored)
    merged.sort(key=lambda c: c.confidence, reverse=True)
    return merged


def _to_track(c: Candidate) -> Track:
    tid = f"yt:{c.video_id}" if c.source == "yt" and c.video_id else f"{c.source}:{c.ext_id}"
    return Track(
        id=tid,
        title=c.title,
        artists=c.artist,
        artist_id="",
        album=c.album,
        album_id="",
        duration=c.duration or 0,
        cover_url=c.cover,
        thumb_url=c.thumb or c.cover,
        year=c.year,
        track_no=0,
        video_id=c.video_id,
        genre=c.genre,
    )


async def search(query: str, limit: int = RESULT_LIMIT) -> list[Track]:
    raw = (query or "").strip()
    if not raw:
        return []

    cache_key = _norm(raw)
    now = time.monotonic()
    hit = _result_cache.get(cache_key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]

    variants = _variants(raw)

    # 1-bosqich: asosiy variant, barcha manbalar parallel.
    cands = await _gather(variants[0], use_youtube=True)
    ranked = _rank(raw, cands)
    strong = [c for c in ranked if c.confidence >= STRONG_CONF]

    # 2-bosqich: zaif bo'lsa — qo'shimcha variantlar (transliteratsiya, tozalash).
    if len(strong) < 3 and len(variants) > 1:
        for v in variants[1:]:
            cands += await _gather(v, use_youtube=False)
        ranked = _rank(raw, cands)
        strong = [c for c in ranked if c.confidence >= STRONG_CONF]

    # 3-bosqich (oxirgi chora): hech narsa yo'q — YouTube'ni har variant bilan kengaytiramiz.
    if not ranked:
        for v in variants:
            cands += await _youtube(v)
        ranked = _rank(raw, cands)

    tracks = [_to_track(c) for c in ranked[:limit]]
    _result_cache[cache_key] = (now, tracks)
    while len(_result_cache) > _CACHE_MAX:
        _result_cache.pop(next(iter(_result_cache)))
    return tracks
