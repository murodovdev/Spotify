"""Akustik-birinchi (acoustic-first) musiqiy o'xshashlik dvigateli.

Maqsad — trekka *ovozi jihatidan* o'xshash qo'shiqlarni tavsiya qilish: kayfiyat,
temp, energiya va sonik xarakteri mos keladigan treklar. Faqat janr yoki ijrochi
emas. "Bu qo'shiqni yaxshi ko'rsam, xuddi shu tuyg'uni beradigan yana qanday
qo'shiqlar bor?" — degan savolga javob beradi.

Signallar (og'irligi bo'yicha, yuqoridan pastga) — barchasi bepul ochiq manbalardan:
  • Kayfiyat / vibe / uslub  — Last.fm jamoaviy teglari (teg vektorlari kosinusi)
  • "Sounds-like" xatti-harakat — Last.fm track.getSimilar jamoaviy mos kelishi
  • Temp (BPM)               — Deezer bpm (yarim/ikki barobar tempni hisobga oladi)
  • Energiya / balandlik      — Deezer gain
  • Janr mosligi              — faqat kichik yordamchi signal
Mashhurlik hech qachon asosiy omil emas — faqat teng ballarni ajratish uchun.

Kandidatlarni yig'ish Last.fm getSimilar (xulq-atvorga asoslangan sound-alikelar)
bilan seedning eng kuchli kayfiyat teglaridagi tag.getTopTracks (turli ijrochilar,
bir xil vibe) ni birlashtiradi — shu sabab tavsiyalar vibe mos kelganda janr
chegaralarini kesib o'ta oladi.

Last.fm kaliti bo'lmasa — janr/davr qidiruviga (temp/energiya bo'yicha qayta
tartiblangan) qaytadi.
"""

import asyncio
import logging
import math
import re
import unicodedata
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher

import aiohttp

from bot.services.spotify import Track, spotify

log = logging.getLogger(__name__)

ITUNES_URL = "https://itunes.apple.com/search"
DEEZER_SEARCH_URL = "https://api.deezer.com/search"
DEEZER_TRACK_URL = "https://api.deezer.com/track"
LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)

# Yig'ish/boyitish cheklovlari — Telegram bot uchun kechikishni jilovlash.
SIMILAR_FETCH  = 40   # Last.fm getSimilar dan olinadigan xom kandidatlar
TAG_TOP_N      = 3    # seedning nechta eng kuchli tegidan kengaytiramiz
TAG_TRACKS     = 12   # har teg bo'yicha nechta trek
ENRICH_CAP     = 24   # nechta kandidat to'liq boyitiladi (tarmoq murojaatlari)
CONCURRENCY    = 8    # bir vaqtdagi boyitish oqimi
PER_ARTIST_CAP = 2    # bir ijrochidan maksimal tavsiya (xilma-xillik uchun)
SEED_ARTIST_CAP = 1   # seed ijrochisidan maksimal (o'sha ijrochi hukmronligini oldini olish)

# O'lchov og'irliklari — akustik/musiqiy signallar janrdan ancha ustun.
#   akustik (teglar+temp+energiya) = 0.66,  jamoaviy = 0.24,  janr = 0.10
W_TAGS   = 0.34   # kayfiyat / vibe / uslub
W_LASTFM = 0.24   # jamoaviy "sounds like"
W_TEMPO  = 0.20   # temp (BPM)
W_ENERGY = 0.12   # energiya / balandlik
W_GENRE  = 0.10   # janr mosligi — eng kichik signal

# Umumiy janrlar → juda keng bo'lgani uchun teg kosinusida pasaytiriladi.
_BROAD_TAGS = {
    "pop", "rock", "electronic", "hip hop", "hip-hop", "rap", "indie",
    "alternative", "dance", "music", "favorites", "seen live", "awesome",
    "favourite", "favorite songs", "love", "spotify", "00s", "10s", "under 2000 listeners",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def _base_title(title: str) -> str:
    """Versiya belgilarini (Remix), [Live], feat. X — dedup kaliti uchun olib tashlaydi."""
    return _norm(re.sub(r"[\(\[\{].*?[\)\]\}]", " ", title or ""))


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _genre_tokens(genre: str) -> set[str]:
    return {t for t in _norm(genre).split() if len(t) > 1}


# ─── Ma'lumot strukturalari ───────────────────────────────────────────────────

@dataclass
class _Profile:
    """Seed trekining akustik profili."""
    tags: dict[str, float] = field(default_factory=dict)
    bpm: float = 0.0
    gain: float = 0.0            # Deezer gain (dB, odatda manfiy); 0.0 = noma'lum
    genre_tokens: set[str] = field(default_factory=set)
    artist_norm: str = ""
    title_key: str = ""


@dataclass
class _Cand:
    """Boyitilgan kandidat — yuklab olinadigan Track + akustik xususiyatlar."""
    track: Track
    tags: dict[str, float] = field(default_factory=dict)
    bpm: float = 0.0
    gain: float = 0.0
    lastfm: float = 0.0         # 0..1 jamoaviy mos kelish (teg manbasida 0)
    rank: int = 0               # Deezer mashhurlik — faqat teng ballarni ajratish
    source: str = ""


# ─── Last.fm chaqiruvlari ─────────────────────────────────────────────────────

async def _lastfm(session: aiohttp.ClientSession, method: str, key: str, **params) -> dict:
    if not key:
        return {}
    try:
        q = {"method": method, "api_key": key, "format": "json", "autocorrect": "1", **params}
        async with session.get(LASTFM_URL, params=q, timeout=_HTTP_TIMEOUT) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json(content_type=None)
    except Exception:
        return {}
    if not isinstance(data, dict) or data.get("error"):
        return {}
    return data


async def _similar_tracks(
    session: aiohttp.ClientSession, artist: str, title: str, key: str, limit: int,
) -> list[tuple[str, str, float]]:
    """track.getSimilar → [(artist, title, match 0..1)]."""
    data = await _lastfm(session, "track.getSimilar", key, artist=artist, track=title, limit=str(limit))
    raw = (data.get("similartracks") or {}).get("track") or []
    out: list[tuple[str, str, float]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        art = item.get("artist")
        if not isinstance(art, dict):
            continue
        out.append((art.get("name") or "", item.get("name") or "", float(item.get("match") or 0.0)))
    return out


def _parse_tags(raw) -> dict[str, float]:
    """Last.fm teglar ro'yxati → {teg: og'irlik 0..1}, umumiy janrlar pasaytirilgan."""
    tags: dict[str, float] = {}
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = _norm(item.get("name") or "")
        if not name:
            continue
        weight = float(item.get("count") or 0) / 100.0
        if weight <= 0:
            weight = 0.4
        if name in _BROAD_TAGS:
            weight *= 0.35
        tags[name] = max(tags.get(name, 0.0), weight)
    # eng kuchli 15 teg
    return dict(sorted(tags.items(), key=lambda kv: kv[1], reverse=True)[:15])


async def _track_tags(session: aiohttp.ClientSession, artist: str, title: str, key: str) -> dict[str, float]:
    data = await _lastfm(session, "track.getTopTags", key, artist=artist, track=title)
    tags = _parse_tags((data.get("toptags") or {}).get("tag"))
    if tags:
        return tags
    # Trek teglari yo'q bo'lsa — ijrochi teglariga qaytamiz (kamroq aniq).
    data = await _lastfm(session, "artist.getTopTags", key, artist=artist)
    return {k: v * 0.7 for k, v in _parse_tags((data.get("toptags") or {}).get("tag")).items()}


async def _tag_top_tracks(session: aiohttp.ClientSession, tag: str, key: str, limit: int) -> list[tuple[str, str]]:
    data = await _lastfm(session, "tag.getTopTracks", key, tag=tag, limit=str(limit))
    raw = (data.get("tracks") or {}).get("track") or []
    out: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        art = item.get("artist")
        art_name = art.get("name") if isinstance(art, dict) else ""
        out.append((art_name or "", item.get("name") or ""))
    return out


# ─── Deezer akustik xususiyatlari ─────────────────────────────────────────────

def _deezer_track(item: dict) -> Track | None:
    if not item or not item.get("id"):
        return None
    album = item.get("album") or {}
    artist = item.get("artist") or {}
    return Track(
        id=f"dz:{item['id']}",
        title=item.get("title") or "",
        artists=artist.get("name") or "",
        artist_id="",
        album=album.get("title") or "",
        album_id="",
        duration=int(item.get("duration") or 0),
        cover_url=album.get("cover_xl") or album.get("cover_big") or "",
        thumb_url=album.get("cover_medium") or "",
        year="",
        track_no=0,
        genre="",
    )


async def _deezer_features(
    session: aiohttp.ClientSession, artist: str, title: str,
) -> tuple[Track | None, float, float, int]:
    """Deezer'dan (Track, bpm, gain, rank). bpm/gain to'liq trek endpointida bo'ladi."""
    async def _search(q: str) -> dict | None:
        try:
            async with session.get(DEEZER_SEARCH_URL, params={"q": q, "limit": 3}, timeout=_HTTP_TIMEOUT) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
        except Exception:
            return None
        for it in data.get("data") or []:
            if _sim(it.get("title") or "", title) > 0.55 and _sim((it.get("artist") or {}).get("name") or "", artist) > 0.45:
                return it
        d = data.get("data") or []
        return d[0] if d else None

    item = await _search(f'artist:"{artist}" track:"{title}"') or await _search(f"{artist} {title}")
    if not item:
        return None, 0.0, 0.0, 0

    track = _deezer_track(item)
    rank = int(item.get("rank") or 0)
    bpm, gain = 0.0, 0.0
    try:
        async with session.get(f"{DEEZER_TRACK_URL}/{item['id']}", timeout=_HTTP_TIMEOUT) as resp:
            if resp.status == 200:
                full = await resp.json(content_type=None)
                bpm = float(full.get("bpm") or 0.0)
                gain = float(full.get("gain") or 0.0)
    except Exception:
        pass
    return track, bpm, gain, rank


# ─── iTunes resolver (janr + muqova beradi) ───────────────────────────────────

async def _itunes_lookup(session: aiohttp.ClientSession, artist: str, title: str) -> Track | None:
    try:
        params = {"term": f"{artist} {title}", "entity": "song", "limit": "4", "country": "US"}
        async with session.get(ITUNES_URL, params=params, timeout=_HTTP_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
    except Exception:
        return None

    for item in data.get("results") or []:
        it_artist = item.get("artistName") or ""
        it_title  = item.get("trackName") or ""
        if _sim(it_title, title) > 0.6 and _sim(it_artist, artist) > 0.5:
            art = item.get("artworkUrl100") or ""
            return Track(
                id=f"it:{item.get('trackId', '')}",
                title=it_title,
                artists=it_artist,
                artist_id="",
                album=item.get("collectionName") or "",
                album_id="",
                duration=round((item.get("trackTimeMillis") or 0) / 1000),
                cover_url=art.replace("100x100", "600x600"),
                thumb_url=art,
                year=(item.get("releaseDate") or "")[:4],
                track_no=0,
                video_id="",
                genre=item.get("primaryGenreName") or "",
            )
    return None


def _merge_tracks(primary: Track | None, secondary: Track | None) -> Track | None:
    """iTunes (janrli) trekni afzal ko'radi, bo'sh maydonlarni Deezer'dan to'ldiradi."""
    if primary is None:
        return secondary
    if secondary is None:
        return primary
    return replace(
        primary,
        album=primary.album or secondary.album,
        cover_url=primary.cover_url or secondary.cover_url,
        thumb_url=primary.thumb_url or secondary.thumb_url,
        duration=primary.duration or secondary.duration,
        year=primary.year or secondary.year,
    )


# ─── Ballash (weighted, acoustic-first) ───────────────────────────────────────

def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[k] * b[k] for k in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _tempo_score(seed: float, cand: float) -> float | None:
    """Temp yaqinligi — yarim/ikki barobar tempni ham hisobga oladi (~12 BPM ichida kuchli)."""
    if seed <= 0 or cand <= 0:
        return None
    d = min(abs(cand - seed), abs(cand - 2 * seed), abs(cand - 0.5 * seed))
    return math.exp(-((d / 12.0) ** 2))


def _energy_score(seed: float, cand: float) -> float | None:
    """Balandlik/energiya yaqinligi (Deezer gain, dB). 0.0 = noma'lum."""
    if seed == 0.0 or cand == 0.0:
        return None
    return math.exp(-((abs(cand - seed) / 4.0) ** 2))


def _genre_score(seed: set[str], cand: set[str]) -> float | None:
    if not seed or not cand:
        return None
    return len(seed & cand) / len(seed | cand)


def _score(seed: _Profile, c: _Cand) -> float:
    """0..1 oralig'idagi umumiy o'xshashlik — mavjud signallar bo'yicha normallashtirilgan."""
    parts: list[tuple[float, float]] = []

    if seed.tags and c.tags:
        parts.append((W_TAGS, _cosine(seed.tags, c.tags)))
    if c.lastfm > 0:
        parts.append((W_LASTFM, min(1.0, c.lastfm)))
    ts = _tempo_score(seed.bpm, c.bpm)
    if ts is not None:
        parts.append((W_TEMPO, ts))
    es = _energy_score(seed.gain, c.gain)
    if es is not None:
        parts.append((W_ENERGY, es))
    gs = _genre_score(seed.genre_tokens, _genre_tokens(c.track.genre))
    if gs is not None:
        parts.append((W_GENRE, gs))

    if not parts:
        return 0.0
    wsum = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / wsum
    # Dalil kam bo'lsa (masalan faqat bitta zaif signal) — biroz pasaytiramiz.
    if wsum < 0.30:
        score *= 0.85
    return score


# ─── Seed profili ─────────────────────────────────────────────────────────────

async def _profile_seed(session: aiohttp.ClientSession, track: Track, key: str) -> _Profile:
    artist = track.artists or track.title
    title = track.title

    tags, feats, itrack = await asyncio.gather(
        _track_tags(session, artist, title, key),
        _deezer_features(session, artist, title),
        _itunes_lookup(session, artist, title),
        return_exceptions=True,
    )
    tags   = tags if isinstance(tags, dict) else {}
    _, bpm, gain, _ = feats if isinstance(feats, tuple) else (None, 0.0, 0.0, 0)
    it_genre = itrack.genre if isinstance(itrack, Track) else ""

    return _Profile(
        tags=tags,
        bpm=bpm,
        gain=gain,
        genre_tokens=_genre_tokens(track.genre or it_genre),
        artist_norm=_norm(artist),
        title_key=_base_title(title),
    )


# ─── Kandidatlarni yig'ish (recall) ───────────────────────────────────────────

async def _gather_candidates(
    session: aiohttp.ClientSession, track: Track, seed: _Profile, key: str,
) -> list[tuple[str, str, float, str]]:
    """(artist, title, lastfm_match, source) ro'yxati — dedup qilingan, seed olib tashlangan."""
    artist = track.artists or track.title

    top_tags = list(seed.tags.keys())[:TAG_TOP_N]
    similar_task = _similar_tracks(session, artist, track.title, key, SIMILAR_FETCH)
    tag_tasks = [_tag_top_tracks(session, tg, key, TAG_TRACKS) for tg in top_tags]

    results = await asyncio.gather(similar_task, *tag_tasks, return_exceptions=True)
    similar = results[0] if isinstance(results[0], list) else []
    tag_lists = [r for r in results[1:] if isinstance(r, list)]

    # (artist_norm, base_title) bo'yicha birlashtirish; eng katta lastfm mosligini saqlaymiz.
    merged: dict[tuple[str, str], tuple[str, str, float, str]] = {}

    def add(a: str, ti: str, m: float, src: str) -> None:
        if not a or not ti:
            return
        base = _base_title(ti)
        if base == seed.title_key:  # o'sha qo'shiqning boshqa versiyasi — o'tkazamiz
            return
        k = (_norm(a), base)
        cur = merged.get(k)
        if cur is None or m > cur[2]:
            merged[k] = (a, ti, m, src if cur is None else cur[3])

    for a, ti, m in similar:
        add(a, ti, m, "similar")
    for lst in tag_lists:
        for a, ti in lst:
            add(a, ti, 0.0, "tag")

    return list(merged.values())


# ─── Kandidatlarni boyitish ───────────────────────────────────────────────────

async def _enrich_pairs(
    session: aiohttp.ClientSession,
    pairs: list[tuple[str, str, float, str]],
    key: str,
) -> list[_Cand]:
    """(artist, title, match, source) → yuklab olinadigan Track + akustik xususiyatlar."""
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(a: str, ti: str, match: float, src: str) -> _Cand | None:
        async with sem:
            itrack, tags, feats = await asyncio.gather(
                _itunes_lookup(session, a, ti),
                _track_tags(session, a, ti, key),
                _deezer_features(session, a, ti),
                return_exceptions=True,
            )
        itrack = itrack if isinstance(itrack, Track) else None
        tags   = tags if isinstance(tags, dict) else {}
        dz_track, bpm, gain, rank = feats if isinstance(feats, tuple) else (None, 0.0, 0.0, 0)

        resolved = _merge_tracks(itrack, dz_track)
        if resolved is None:  # yuklab olinadigan manba topilmadi — o'tkazamiz
            return None
        return _Cand(track=resolved, tags=tags, bpm=bpm, gain=gain, lastfm=match, rank=rank, source=src)

    results = await asyncio.gather(*[one(*p) for p in pairs])
    return [r for r in results if r is not None]


# ─── Yakuniy tanlash: ballash, xilma-xillik, cheklovlar ───────────────────────

def _select(seed: _Profile, cands: list[_Cand], limit: int) -> list[Track]:
    scored: list[tuple[float, _Cand]] = []
    for c in cands:
        sc = _score(seed, c)
        # Mashhurlik faqat teng ballarni ajratish uchun (juda kichik ta'sir).
        pop = min(1.0, math.log10(c.rank + 1) / 6.0) if c.rank else 0.0
        scored.append((sc + 0.02 * pop, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    out: list[Track] = []
    artist_count: dict[str, int] = {}
    for sc, c in scored:
        a = _norm(c.track.artists)
        cap = SEED_ARTIST_CAP if a == seed.artist_norm else PER_ARTIST_CAP
        if artist_count.get(a, 0) >= cap:
            continue
        artist_count[a] = artist_count.get(a, 0) + 1
        # Ko'rsatish uchun qulay o'lchov: 50..99% oralig'iga monoton mapping.
        display = min(0.99, 0.5 + 0.5 * max(0.0, min(1.0, _score(seed, c))))
        out.append(replace(c.track, sim=round(display, 3)))
        if len(out) >= limit:
            break
    return out


# ─── Fallback: janr/davr qidiruvi (temp/energiya bo'yicha qayta tartiblangan) ──

_GENRE_QUERIES: dict[str, list[str]] = {
    "pop": ["feel good pop songs", "popular pop hits"],
    "indie": ["indie pop rock songs", "dream pop playlist"],
    "r&b": ["smooth r&b soul songs", "neo soul music"],
    "soul": ["soul music r&b playlist", "neo soul classics"],
    "hip-hop": ["hip hop rap playlist", "rap music hits"],
    "rap": ["rap music hits playlist", "hip hop songs"],
    "rock": ["rock music playlist hits", "alternative rock songs"],
    "metal": ["metal songs playlist", "heavy metal hits"],
    "electronic": ["electronic dance hits", "edm songs playlist"],
    "house": ["house music playlist", "deep house songs"],
    "techno": ["techno electronic music", "melodic techno"],
    "country": ["country music songs", "country pop hits"],
    "jazz": ["smooth jazz music", "jazz standards playlist"],
    "classical": ["classical orchestra music", "piano classical pieces"],
    "reggae": ["reggae music playlist", "dancehall songs"],
    "latin": ["latin pop hits", "reggaeton songs playlist"],
    "folk": ["folk acoustic songs", "singer songwriter folk"],
    "blues": ["blues rock songs", "soul blues music"],
    "k-pop": ["k-pop hits playlist", "korean pop music"],
    "funk": ["funk groove playlist", "funk soul hits"],
    "lo-fi": ["lo-fi hip hop beats", "chill lo-fi music"],
    "acoustic": ["acoustic songs playlist", "acoustic covers"],
}


def _style_queries(track: Track) -> list[str]:
    genre = (track.genre or "").lower().strip()
    year = (track.year or "")[:4]
    decade = f"{year[:3]}0s" if len(year) == 4 else ""

    queries: list[str] = []
    for key, phrases in _GENRE_QUERIES.items():
        if key in genre:
            queries.extend(phrases[:2])
            break
    if decade:
        queries.append(f"{genre} {decade} songs" if genre else f"best songs {decade}")
    if not queries:
        queries.append(f"{genre} songs playlist" if genre else "popular music hits")
    return queries[:3]


async def _via_fallback(track: Track, limit: int) -> list[Track]:
    """Last.fm bo'lmaganda: janr qidiruvi + Deezer temp/energiya bo'yicha qayta tartiblash."""
    from bot.services import search_engine

    session = await spotify.session()
    seed = await _profile_seed(session, track, key="")  # kalitsiz — teglar bo'sh

    queries = _style_queries(track)
    batches = await asyncio.gather(*[search_engine.search(q) for q in queries], return_exceptions=True)

    seen: set[tuple[str, str]] = {(seed.artist_norm, seed.title_key)}
    resolved: list[Track] = []
    for batch in batches:
        if not isinstance(batch, list):
            continue
        for tr in batch:
            base = _base_title(tr.title)
            if base == seed.title_key:
                continue
            k = (_norm(tr.artists), base)
            if k in seen:
                continue
            seen.add(k)
            resolved.append(tr)

    if not resolved:
        return []

    resolved = resolved[:ENRICH_CAP]
    sem = asyncio.Semaphore(CONCURRENCY)

    async def feat(tr: Track) -> _Cand:
        async with sem:
            res = await _deezer_features(session, tr.artists, tr.title)
        _, bpm, gain, rank = res if isinstance(res, tuple) else (None, 0.0, 0.0, 0)
        return _Cand(track=tr, tags={}, bpm=bpm, gain=gain, lastfm=0.0, rank=rank, source="genre")

    cands = await asyncio.gather(*[feat(tr) for tr in resolved])
    selected = _select(seed, list(cands), limit)
    # Signallar zaif bo'lsa ham hech bo'lmaganda janr natijalarini qaytaramiz.
    return selected or resolved[:limit]


# ─── Commumiy interfeys ───────────────────────────────────────────────────────

async def get_similar(track: Track, limit: int = 18) -> list[Track]:
    """`track` ga *ovozi jihatidan* o'xshash treklarni (10–20 ta) qaytaradi.

    Last.fm kaliti sozlangan bo'lsa — akustik-birinchi ko'p signalli reyting
    (kayfiyat teglari + jamoaviy o'xshashlik + temp + energiya + janr).
    Aks holda janr/davr qidiruviga qaytadi. Natijalar to'g'ridan-to'g'ri
    store.remember() + keyboards.search_results() ga uzatilishga tayyor.
    """
    from bot.config import settings

    key = settings.lastfm_api_key
    if not key:
        return await _via_fallback(track, limit)

    try:
        session = await spotify.session()
        seed = await _profile_seed(session, track, key)
        pairs = await _gather_candidates(session, track, seed, key)
        if not pairs:
            log.info("Last.fm hech qanday kandidat bermadi %r — fallback", track.title)
            return await _via_fallback(track, limit)

        # Faqat eng istiqbolli kandidatlarni to'liq boyitamiz (jamoaviy mos → teg).
        pairs.sort(key=lambda p: (p[2], p[3] == "similar"), reverse=True)
        cands = await _enrich_pairs(session, pairs[:ENRICH_CAP], key)
        if not cands:
            return await _via_fallback(track, limit)

        selected = _select(seed, cands, limit)
        if selected:
            return selected
    except Exception:
        log.exception("Akustik tavsiya xatosi %r — fallback", track.title)

    return await _via_fallback(track, limit)
