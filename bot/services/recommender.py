"""Ko'p bosqichli, audio-birinchi musiqiy tavsiya dvigateli (Song Radio uslubida).

Maqsad: "Shu qo'shiq yoqsa — xuddi shunday ESHITILADIGAN yana nima bor?"
Ijrochi/janr/mashhurlik asosiy signal EMAS — faqat yordamchi.

Bosqichlar (barcha manbalar bepul, kalitsiz; Last.fm ixtiyoriy kuchaytirgich):

  1. Seed identifikatsiyasi
     ListenBrainz acr-lookup → kanonik MBID; Deezer → preview/bpm/gain/artist;
     iTunes → janr; Last.fm → treg teglari (kalit bo'lsa).
  2. Kandidat generatsiyasi (parallel, ~150 xom)
     • ListenBrainz similar-recordings — millionlab tinglash sessiyalaridan
       "birga eshitiladi" statistikasi (Spotify Radio'ning xulq-atvor signali)
     • ListenBrainz similar-artists → Deezer top treklar
     • Deezer related-artists top treklari va artist-radio (Deezer Flow)
     • Last.fm getSimilar va kayfiyat-teg treklari (kalit bo'lsa)
  3. Kanonizatsiya: dedup (ijrochi + asosiy sarlavha), seed versiyalari va
     karaoke/nightcore/cover kabi keraksizlarni chiqarib tashlash.
  4. Boyitish (keshbirinchi, SQLite `rec_features`): Deezer id/preview/rank,
     iTunes janr, AcousticBrainz mood/danceability (MBID bo'yicha batch).
  5. Audio tahlil: seed va top kandidatlarning 30s preview'lari lokal MIR
     (tempo, energiya, tembr-embedding, chroma) — audio_analysis.py, doimiy kesh.
  6. Ballash: mavjudlik bo'yicha normallashgan vaznli yig'indi —
     audio 0.40 · xulq-atvor 0.28 · teglar 0.14 · janr 0.08 · davr 0.06 · davomiylik 0.04.
     Mashhurlik ballga KIRMAYDI (faqat kam-mashhur trekka mayda discovery-bonus).
  7. Tanlash: MMR (o'xshashlik − ortiqchalik), ijrochi cheklovlari
     (seed ijrochisi ≤1, boshqalar ≤2), rotatsiya xotirasi (`rec_shown`) —
     qayta bosilganda YANGI treklar, gem-bonus — kashfiyot uchun.
  8. Sifat darvozasi: past ballar va cover-dublikatlar chiqariladi.

Kechikish: sovuq ~6-9s, iliq (kesh) ~2-4s. Deezer chaqiruvlari token-bucket
bilan cheklanadi (50 req/5s limitiga urilmaslik uchun).
"""

import asyncio
import json
import logging
import math
import random
import re
import ssl
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import aiohttp

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

from bot.services import audio_analysis
from bot.services.audio_analysis import AudioVector
from bot.services.spotify import Track, spotify

log = logging.getLogger(__name__)

# ─── Manba URL'lari ───────────────────────────────────────────────────────────

LB_LABS = "https://labs.api.listenbrainz.org"
LB_SIMILAR_ALGO = (
    "session_based_days_9000_session_300_contribution_5_threshold_15_limit_50_skip_30"
)
LB_ARTIST_ALGO = (
    "session_based_days_7500_session_300_contribution_3_threshold_10_limit_100_filter_True_skip_30"
)
AB_URL = "https://acousticbrainz.org/api/v1/high-level"
DEEZER = "https://api.deezer.com"
ITUNES_URL = "https://itunes.apple.com/search"
LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"

_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)
_LB_TIMEOUT = aiohttp.ClientTimeout(total=15)

# MetaBrainz (listenbrainz/acousticbrainz) sertifikat zanjiri ba'zi OpenSSL
# konfiguratsiyalarida "expired" deb rad etiladi — certifi bundle bilan ishlaydi.
_MB_SSL = ssl.create_default_context(cafile=certifi.where()) if certifi else None

# ─── Cheklovlar / sozlamalar ──────────────────────────────────────────────────

ENRICH_CAP   = 30    # nechta kandidat to'liq boyitiladi
AUDIO_CAP    = 20    # nechta kandidat preview'i lokal tahlil qilinadi
TAGS_CAP     = 20    # nechta kandidat uchun Last.fm teglar olinadi (kalit bo'lsa)
ITUNES_CAP   = 12    # nechta kandidat uchun iTunes janr so'raladi
CONCURRENCY  = 8
AUDIO_CONC   = 5

PER_ARTIST_CAP  = 2   # bitta ijrochidan ko'pi bilan
SEED_ARTIST_CAP = 1   # seed ijrochisidan ko'pi bilan

SHOWN_DAYS   = 14     # rotatsiya oynasi
POOL_TTL     = 600.0  # kandidat hovuzi keshining umri (soniya)
FEAT_RETRY_DAYS = 7   # muvaffaqiyatsiz lookup'ni qachondan keyin qayta urinish

# Ballash og'irliklari — audio birinchi, metadata yordamchi.
W_AUDIO = 0.40   # lokal DSP + AcousticBrainz — trek qanday ESHITILADI
W_BEHAV = 0.28   # ListenBrainz/Last.fm — odamlar birga nimani tinglaydi
W_TAGS  = 0.14   # kayfiyat/uslub teglari (Last.fm kaliti bo'lsa)
W_GENRE = 0.08   # janr tokenlari — kichik yordamchi
W_ERA   = 0.06   # davr yaqinligi
W_DUR   = 0.04   # davomiylik oqilonaligi (10 daqiqalik mixlarni chetlaydi)

SCORE_FLOOR  = 0.30
MMR_LAMBDA   = 0.35   # ortiqchalik jarimasi kuchi
ROT_PENALTY  = 0.28   # yaqinda ko'rsatilgan trek jarimasi
GEM_BONUS    = 0.02   # kam-mashhur (discovery) bonus

# Sarlavhasida shu so'zlar bo'lgan kandidatlar tashlanadi (seed'da bo'lmasa)
_JUNK = (
    "karaoke", "tribute", "nightcore", "8d", "sped up", "speed up", "slowed",
    "reverb", "bass boosted", "instrumental", "cover", "remix", "mashup",
    "reaction", "1 hour", "10 hour", "loop", "ringtone",
)

# Versiya belgilari — tashlanmaydi, lekin studiya versiyasidan pastroq ball oladi
_VERSION_PEN = re.compile(r"\b(live|remaster(?:ed)?|demo|sped ?up|slowed|acoustic|edit)\b", re.I)

_BROAD_TAGS = {
    "pop", "rock", "electronic", "hip hop", "hip-hop", "rap", "indie",
    "alternative", "dance", "music", "favorites", "seen live", "awesome",
    "favourite", "favorite songs", "love", "spotify", "00s", "10s",
    "under 2000 listeners", "american", "british", "male vocalists",
    "female vocalists",
}


# ─── Matn normalizatsiyasi ────────────────────────────────────────────────────

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def _base_title(title: str) -> str:
    """Versiya belgilari (Remix), [Live], feat. — dedup kaliti uchun olib tashlanadi."""
    t = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", title or "")
    t = re.sub(r"\b(feat|ft)\.?\s+.*$", " ", t, flags=re.I)
    return _norm(t)


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _feat_key(artists: str, title: str) -> str:
    return f"{_norm(artists)}|{_base_title(title)}"


def _genre_tokens(genre: str) -> set[str]:
    return {t for t in _norm(genre).split() if len(t) > 1}


def _is_junk(title: str, seed_title: str) -> bool:
    low = (title or "").lower()
    seed_low = (seed_title or "").lower()
    return any(w in low and w not in seed_low for w in _JUNK)


def _seed_names(track: Track) -> tuple[str, str]:
    """YouTube'dan kelgan treklar uchun (kanal — "Artist - Title") tozalash."""
    artist = re.sub(r"\s*-\s*topic\s*$", "", (track.artists or "").strip(), flags=re.I)
    title = (track.title or "").strip()
    m = re.match(r"^(.{2,60}?)\s*[-–—]\s*(.{2,90})$", title)
    if m:
        left, right = m.group(1).strip(), m.group(2).strip()
        if not artist or _sim(left, artist) > 0.55:
            return (artist or left), right
    return (artist or title), title


# ─── Deezer token-bucket (50 req / 5s API limiti; xavfsiz zaxira bilan) ───────

class _RateLimiter:
    def __init__(self, calls: int, per: float) -> None:
        self._calls, self._per = calls, per
        self._stamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._stamps = [t for t in self._stamps if now - t < self._per]
                if len(self._stamps) < self._calls:
                    self._stamps.append(now)
                    return
                wait = self._per - (now - self._stamps[0]) + 0.05
            await asyncio.sleep(max(wait, 0.05))


_dz_limit = _RateLimiter(45, 5.0)


# ─── Umumiy HTTP helper ───────────────────────────────────────────────────────

async def _get_json(
    session: aiohttp.ClientSession, url: str, params: dict | None = None,
    timeout: aiohttp.ClientTimeout = _HTTP_TIMEOUT,
    ssl_ctx: ssl.SSLContext | None = None,
):
    try:
        kwargs = {"ssl": ssl_ctx} if ssl_ctx is not None else {}
        async with session.get(url, params=params, timeout=timeout, **kwargs) as resp:
            if resp.status != 200:
                return None
            return await resp.json(content_type=None)
    except Exception:
        return None


async def _dz_get(session: aiohttp.ClientSession, path: str, params: dict | None = None):
    await _dz_limit.acquire()
    data = await _get_json(session, f"{DEEZER}{path}", params)
    if isinstance(data, dict) and data.get("error"):
        return None
    return data


# ─── ListenBrainz Labs (kalitsiz kollaborativ signal) ─────────────────────────

async def _lb_lookup(session, artist: str, title: str) -> tuple[str, list[str]]:
    """(kanonik recording MBID, artist MBID'lar). Topilmasa ("", [])."""
    data = await _get_json(
        session, f"{LB_LABS}/acr-lookup/json",
        {"artist_credit_name": artist, "recording_name": title},
        timeout=_LB_TIMEOUT, ssl_ctx=_MB_SSL,
    )
    if not isinstance(data, list) or not data:
        return "", []
    row = data[0]
    got_artist = row.get("artist_credit_name") or ""
    got_title = row.get("recording_name") or ""
    # acr-lookup fuzzy — noto'g'ri trekka yopishib qolmaslik uchun tekshiramiz
    if _sim(got_title, title) < 0.55 or _sim(got_artist, artist) < 0.45:
        return "", []
    return row.get("recording_mbid") or "", list(row.get("artist_mbids") or [])


async def _lb_similar_recordings(session, mbid: str) -> list[tuple[str, str, str, float]]:
    """[(artist, title, mbid, score)] — tinglash sessiyalariga asoslangan."""
    if not mbid:
        return []
    data = await _get_json(
        session, f"{LB_LABS}/similar-recordings/json",
        {"recording_mbids": mbid, "algorithm": LB_SIMILAR_ALGO},
        timeout=_LB_TIMEOUT, ssl_ctx=_MB_SSL,
    )
    out: list[tuple[str, str, str, float]] = []
    for row in data or []:
        if not isinstance(row, dict):
            continue
        out.append((
            row.get("artist_credit_name") or "",
            row.get("recording_name") or "",
            row.get("recording_mbid") or "",
            float(row.get("score") or 0.0),
        ))
    return out


async def _lb_similar_artists(session, artist_mbids: list[str]) -> list[str]:
    """O'xshash ijrochi nomlari (eng kuchlisidan boshlab)."""
    if not artist_mbids:
        return []
    data = await _get_json(
        session, f"{LB_LABS}/similar-artists/json",
        {"artist_mbids": artist_mbids[0], "algorithm": LB_ARTIST_ALGO},
        timeout=_LB_TIMEOUT, ssl_ctx=_MB_SSL,
    )
    names: list[str] = []
    for row in data or []:
        name = row.get("name") if isinstance(row, dict) else None
        if name and name not in names:
            names.append(name)
    return names


# ─── AcousticBrainz (Essentia modellaridan mood/danceability) ─────────────────

_AB_FIELDS = {
    "dance": ("danceability", "danceable"),
    "aggr": ("mood_aggressive", "aggressive"),
    "happy": ("mood_happy", "happy"),
    "party": ("mood_party", "party"),
    "relax": ("mood_relaxed", "relaxed"),
    "sad": ("mood_sad", "sad"),
    "acoustic": ("mood_acoustic", "acoustic"),
    "electronic": ("mood_electronic", "electronic"),
    "voice": ("voice_instrumental", "voice"),
    "tonal": ("tonal_atonal", "tonal"),
    "bright": ("timbre", "bright"),
}


def _ab_condense(doc: dict) -> dict:
    hl = doc.get("highlevel") or {}
    out: dict[str, float] = {}
    for fld, (name, cls) in _AB_FIELDS.items():
        v = ((hl.get(name) or {}).get("all") or {}).get(cls)
        if v is not None:
            out[fld] = round(float(v), 3)
    return out


async def _ab_batch(session, mbids: list[str]) -> dict[str, dict]:
    """MBID → ixcham mood-vektor. 25 talik guruhlarda so'raladi."""
    result: dict[str, dict] = {}
    for i in range(0, len(mbids), 25):
        chunk = mbids[i : i + 25]
        data = await _get_json(session, AB_URL, {"recording_ids": ";".join(chunk)}, ssl_ctx=_MB_SSL)
        if not isinstance(data, dict):
            continue
        for mbid in chunk:
            doc = data.get(mbid)
            if isinstance(doc, dict):
                sub = doc.get("0")
                if isinstance(sub, dict):
                    cond = _ab_condense(sub)
                    if cond:
                        result[mbid] = cond
    return result


def _ab_sim(a: dict | None, b: dict | None) -> float | None:
    if not a or not b:
        return None
    shared = [k for k in a if k in b]
    if len(shared) < 4:
        return None
    return 1.0 - sum(abs(a[k] - b[k]) for k in shared) / len(shared)


# ─── Last.fm (ixtiyoriy kuchaytirgich) ────────────────────────────────────────

async def _lastfm(session, method: str, key: str, **params) -> dict:
    if not key:
        return {}
    q = {"method": method, "api_key": key, "format": "json", "autocorrect": "1", **params}
    data = await _get_json(session, LASTFM_URL, q)
    if not isinstance(data, dict) or data.get("error"):
        return {}
    return data


async def _fm_similar(session, artist: str, title: str, key: str) -> list[tuple[str, str, float]]:
    data = await _lastfm(session, "track.getSimilar", key, artist=artist, track=title, limit="50")
    out = []
    for item in (data.get("similartracks") or {}).get("track") or []:
        if isinstance(item, dict) and isinstance(item.get("artist"), dict):
            out.append((
                item["artist"].get("name") or "", item.get("name") or "",
                float(item.get("match") or 0.0),
            ))
    return out


def _parse_tags(raw) -> dict[str, float]:
    tags: dict[str, float] = {}
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = _norm(item.get("name") or "")
        if not name:
            continue
        w = float(item.get("count") or 0) / 100.0 or 0.4
        if name in _BROAD_TAGS:
            w *= 0.35
        tags[name] = max(tags.get(name, 0.0), w)
    return dict(sorted(tags.items(), key=lambda kv: kv[1], reverse=True)[:15])


async def _fm_track_tags(session, artist: str, title: str, key: str) -> dict[str, float]:
    """Faqat TREK teglari — ijrochi teglariga qaytish yo'q (ijrochi biasidan qochamiz)."""
    data = await _lastfm(session, "track.getTopTags", key, artist=artist, track=title)
    return _parse_tags((data.get("toptags") or {}).get("tag"))


async def _fm_tag_tracks(session, tag: str, key: str, limit: int) -> list[tuple[str, str]]:
    data = await _lastfm(session, "tag.getTopTracks", key, tag=tag, limit=str(limit))
    out = []
    for item in (data.get("tracks") or {}).get("track") or []:
        if isinstance(item, dict):
            art = item.get("artist")
            out.append(((art or {}).get("name") or "", item.get("name") or ""))
    return out


# ─── Deezer ───────────────────────────────────────────────────────────────────

def _fill_dz(f: dict, item: dict) -> None:
    """Deezer trek obyektidan feat maydonlarini to'ldiradi (search/top/radio formati)."""
    album = item.get("album") or {}
    artist = item.get("artist") or {}
    f["dz_id"] = int(item.get("id") or 0)
    f["dz_artist_id"] = int(artist.get("id") or 0)
    f["rank"] = int(item.get("rank") or 0)
    f["preview"] = item.get("preview") or f.get("preview") or ""
    f["duration"] = int(item.get("duration") or 0) or f.get("duration", 0)
    f["album"] = album.get("title") or f.get("album", "")
    f["cover"] = album.get("cover_xl") or album.get("cover_big") or f.get("cover", "")
    f["thumb"] = album.get("cover_medium") or f.get("thumb", "")
    if item.get("release_date"):
        f["year"] = str(item["release_date"])[:4]


async def _dz_search_best(session, artist: str, title: str) -> dict | None:
    async def _search(q: str) -> dict | None:
        data = await _dz_get(session, "/search", {"q": q, "limit": 8})
        best, best_key = None, (0.0, 0)
        for it in (data or {}).get("data") or []:
            s = 0.6 * _sim(it.get("title") or "", title) + 0.4 * _sim(
                (it.get("artist") or {}).get("name") or "", artist
            )
            if s <= 0.55:
                continue
            # Matn deyarli teng bo'lsa — KANONIK (mashhur) nashrni afzal ko'ramiz:
            # arvoh qayta-yuklamalar rank≈0 bilan keladi va radio/related bermaydi.
            key = (round(s, 1), int(it.get("rank") or 0))
            if key > best_key:
                best, best_key = it, key
        return best

    # Oddiy so'rov deyarli har doim yetarli (1 chaqiruv); topilmasa aniq sintaksis.
    return (
        await _search(f"{artist} {title}")
        or await _search(f'artist:"{artist}" track:"{title}"')
    )


async def _dz_track_detail(session, dz_id: int) -> dict | None:
    return await _dz_get(session, f"/track/{dz_id}")


async def _dz_artist_radio(session, artist_id: int, limit: int = 25) -> list[dict]:
    data = await _dz_get(session, f"/artist/{artist_id}/radio", {"limit": limit})
    return (data or {}).get("data") or []


async def _dz_related_artists(session, artist_id: int, limit: int = 8) -> list[dict]:
    data = await _dz_get(session, f"/artist/{artist_id}/related", {"limit": limit})
    return (data or {}).get("data") or []


async def _dz_artist_top(session, artist_id: int, limit: int = 4) -> list[dict]:
    data = await _dz_get(session, f"/artist/{artist_id}/top", {"limit": limit})
    return (data or {}).get("data") or []


async def _dz_find_artist(session, name: str) -> int:
    data = await _dz_get(session, "/search/artist", {"q": name, "limit": 1})
    items = (data or {}).get("data") or []
    if items and _sim(items[0].get("name") or "", name) > 0.6:
        return int(items[0].get("id") or 0)
    return 0


# ─── iTunes (janr uchun) ──────────────────────────────────────────────────────

async def _itunes_lookup(session, artist: str, title: str) -> dict | None:
    data = await _get_json(
        session, ITUNES_URL,
        {"term": f"{artist} {title}", "entity": "song", "limit": "4", "country": "US"},
    )
    for item in (data or {}).get("results") or []:
        if _sim(item.get("trackName") or "", title) > 0.6 and _sim(item.get("artistName") or "", artist) > 0.5:
            return item
    return None


# ─── Xususiyatlar keshi (SQLite, doimiy) ──────────────────────────────────────

FEAT_V = 2  # v1: SSL tuzatishidan oldingi (LB'siz) yozuvlar — bekor qilingan


def _new_feat(artists: str, title: str) -> dict:
    return {
        "v": FEAT_V, "artists": artists, "title": title,
        "dz_id": 0, "dz_artist_id": 0, "rank": 0, "preview": "",
        "duration": 0, "album": "", "cover": "", "thumb": "", "year": "",
        "genre": "", "it_id": "", "mbid": "", "tags": {},
        "audio": None, "ab": None, "checked": {},
    }


def _stale(f: dict, what: str) -> bool:
    ts = (f.get("checked") or {}).get(what, 0.0)
    return time.time() - ts > FEAT_RETRY_DAYS * 86400


def _mark(f: dict, what: str) -> None:
    f.setdefault("checked", {})[what] = time.time()


async def _load_feat(artists: str, title: str) -> dict:
    from bot.db import repo

    key = _feat_key(artists, title)
    raw = await repo.rec_feat_get(key)
    if raw:
        try:
            f = json.loads(raw)
            if f.get("v") == FEAT_V:
                return f
        except Exception:
            pass
    return _new_feat(artists, title)


async def _save_feat(f: dict) -> None:
    from bot.db import repo

    key = _feat_key(f["artists"], f["title"])
    try:
        await repo.rec_feat_put(key, json.dumps(f, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        log.debug("rec_features yozishda xato", exc_info=True)


async def _resolve_feat(
    session, artists: str, title: str, *,
    dz_item: dict | None = None, mbid: str = "",
    want_detail: bool = False, want_genre: bool = False,
) -> dict:
    """Feat'ni keshdan oladi, yetishmagan qismlarni tarmoqdan to'ldiradi va saqlaydi."""
    f = await _load_feat(artists, title)
    changed = False

    if mbid and not f.get("mbid"):
        f["mbid"] = mbid
        changed = True
    if dz_item and not f.get("dz_id"):
        _fill_dz(f, dz_item)
        changed = True

    if not f.get("dz_id") and _stale(f, "dz"):
        item = await _dz_search_best(session, artists, title)
        _mark(f, "dz")
        changed = True
        if item:
            _fill_dz(f, item)

    if want_detail and f.get("dz_id") and not f.get("preview") and _stale(f, "dzd"):
        detail = await _dz_track_detail(session, f["dz_id"])
        _mark(f, "dzd")
        changed = True
        if detail:
            f["preview"] = detail.get("preview") or ""
            f["bpm"] = float(detail.get("bpm") or 0.0)
            f["gain"] = float(detail.get("gain") or 0.0)
            if detail.get("release_date"):
                f["year"] = str(detail["release_date"])[:4]

    if want_genre and not f.get("genre") and _stale(f, "it"):
        item = await _itunes_lookup(session, artists, title)
        _mark(f, "it")
        changed = True
        if item:
            f["genre"] = item.get("primaryGenreName") or ""
            f["it_id"] = str(item.get("trackId") or "")
            f["year"] = f.get("year") or (item.get("releaseDate") or "")[:4]
            if not f.get("cover"):
                art = item.get("artworkUrl100") or ""
                f["cover"] = art.replace("100x100", "600x600")
                f["thumb"] = art
            f["duration"] = f.get("duration") or round((item.get("trackTimeMillis") or 0) / 1000)
            f["album"] = f.get("album") or item.get("collectionName") or ""

    if changed:
        await _save_feat(f)
    return f


def _feat_track(f: dict, score: float) -> Track | None:
    """Feat → yuklab olinadigan Track (dz: yoki it: id)."""
    if f.get("dz_id"):
        tid = f"dz:{f['dz_id']}"
    elif f.get("it_id"):
        tid = f"it:{f['it_id']}"
    else:
        return None
    return Track(
        id=tid, title=f["title"], artists=f["artists"], artist_id="",
        album=f.get("album") or "", album_id="",
        duration=int(f.get("duration") or 0),
        cover_url=f.get("cover") or "", thumb_url=f.get("thumb") or f.get("cover") or "",
        year=f.get("year") or "", track_no=0, genre=f.get("genre") or "",
        sim=round(max(0.0, min(1.0, score)), 3),
    )


# ─── Kandidat modeli va generatsiya ───────────────────────────────────────────

@dataclass
class _Cand:
    artists: str
    title: str
    key: str
    mbid: str = ""
    lb: float = 0.0                 # ListenBrainz score (normallashgan 0..1)
    fm: float = 0.0                 # Last.fm match 0..1
    sources: set[str] = field(default_factory=set)
    dz_item: dict | None = None     # radio/top javobidan tayyor Deezer obyekti
    feat: dict = field(default_factory=dict)

    @property
    def behavioral(self) -> float:
        base = max(self.lb, self.fm)
        if base <= 0:
            # Ballanmagan-lekin-xulq-atvorli manbalar uchun mo''tadil default
            if self.sources & {"radio", "related", "lbart"}:
                base = 0.30
            elif "tag" in self.sources:
                base = 0.15
        bonus = 0.08 * max(0, len(self.sources) - 1)  # manbalar kelishuvi kuchli signal
        return min(1.0, base + min(bonus, 0.16))


async def _generate(session, seed: dict, artist: str, title: str, key: str) -> list[_Cand]:
    """Barcha manbalardan kandidatlar — dedup qilingan, seed chiqarib tashlangan."""
    seed_key = _feat_key(artist, title)
    seed_base = _base_title(title)

    lb_task = _lb_similar_recordings(session, seed.get("mbid") or "")
    fm_task = _fm_similar(session, artist, title, key) if key else asyncio.sleep(0, result=[])
    radio_task = (
        _dz_artist_radio(session, seed["dz_artist_id"])
        if seed.get("dz_artist_id") else asyncio.sleep(0, result=[])
    )
    related_task = (
        _dz_related_artists(session, seed["dz_artist_id"])
        if seed.get("dz_artist_id") else asyncio.sleep(0, result=[])
    )
    lbart_task = _lb_similar_artists(session, seed.get("artist_mbids") or [])
    tag_names = list((seed.get("tags") or {}).keys())[:2]
    tag_tasks = [_fm_tag_tracks(session, tg, key, 8) for tg in tag_names] if key else []

    lb_res, fm_res, radio_res, related_res, lbart_res, *tag_res = await asyncio.gather(
        lb_task, fm_task, radio_task, related_task, lbart_task, *tag_tasks,
        return_exceptions=True,
    )
    lb_res = lb_res if isinstance(lb_res, list) else []
    fm_res = fm_res if isinstance(fm_res, list) else []
    radio_res = radio_res if isinstance(radio_res, list) else []
    related_res = related_res if isinstance(related_res, list) else []
    lbart_res = lbart_res if isinstance(lbart_res, list) else []

    merged: dict[str, _Cand] = {}

    def add(a: str, ti: str, src: str, *, mbid="", lb=0.0, fm=0.0, dz_item=None) -> None:
        if not a or not ti or _is_junk(ti, title):
            return
        k = _feat_key(a, ti)
        if k == seed_key or _base_title(ti) == seed_base:
            return
        c = merged.get(k)
        if c is None:
            c = merged[k] = _Cand(artists=a, title=ti, key=k)
        c.sources.add(src)
        c.mbid = c.mbid or mbid
        c.lb = max(c.lb, lb)
        c.fm = max(c.fm, fm)
        if dz_item and c.dz_item is None:
            c.dz_item = dz_item

    # ListenBrainz — log-normallashgan score
    max_lb = max((s for *_, s in lb_res), default=0.0)
    for a, ti, mbid, s in lb_res:
        add(a, ti, "lb", mbid=mbid, lb=math.log1p(s) / math.log1p(max_lb) if max_lb > 0 else 0.0)

    for a, ti, m in fm_res:
        add(a, ti, "fm", fm=min(1.0, m))

    for it in radio_res:
        add((it.get("artist") or {}).get("name") or "", it.get("title") or "", "radio", dz_item=it)

    # Related artists → top treklar (parallel)
    rel_ids = [int(r.get("id") or 0) for r in related_res[:6] if r.get("id")]
    top_lists = await asyncio.gather(
        *[_dz_artist_top(session, rid, 4) for rid in rel_ids], return_exceptions=True
    )
    for lst in top_lists:
        for it in lst if isinstance(lst, list) else []:
            add((it.get("artist") or {}).get("name") or "", it.get("title") or "", "related", dz_item=it)

    # ListenBrainz o'xshash ijrochilar → Deezer top treklar.
    # LB recordings mo'l bo'lsa bu zanjir shart emas — kechikishni tejaymiz.
    lbart_names = [] if len(lb_res) >= 30 else [n for n in lbart_res if _sim(n, artist) < 0.85][:4]
    art_ids = await asyncio.gather(
        *[_dz_find_artist(session, n) for n in lbart_names], return_exceptions=True
    )
    lbart_tops = await asyncio.gather(
        *[_dz_artist_top(session, aid, 3) for aid in art_ids if isinstance(aid, int) and aid],
        return_exceptions=True,
    )
    for lst in lbart_tops:
        for it in lst if isinstance(lst, list) else []:
            add((it.get("artist") or {}).get("name") or "", it.get("title") or "", "lbart", dz_item=it)

    for lst in tag_res:
        for a, ti in lst if isinstance(lst, list) else []:
            add(a, ti, "tag")

    return list(merged.values())


def _interleave(cands: list[_Cand], cap: int) -> list[_Cand]:
    """Manbalar bo'yicha navbatlashtirib top-N — bitta manba hukmronligini oldini oladi."""
    order = ("lb", "radio", "related", "lbart", "fm", "tag")
    buckets: dict[str, list[_Cand]] = {s: [] for s in order}
    for c in sorted(cands, key=lambda c: c.behavioral, reverse=True):
        src = next((s for s in order if s in c.sources), "tag")
        buckets[src].append(c)
    out: list[_Cand] = []
    seen: set[str] = set()
    while len(out) < cap and any(buckets.values()):
        for s in order:
            if buckets[s]:
                c = buckets[s].pop(0)
                if c.key not in seen:
                    seen.add(c.key)
                    out.append(c)
                    if len(out) >= cap:
                        break
    return out


# ─── Boyitish ─────────────────────────────────────────────────────────────────

async def _enrich(session, seed: dict, cands: list[_Cand], key: str) -> list[_Cand]:
    """Feat'lar (kesh-birinchi) + AcousticBrainz batch + lokal audio tahlil + teglar."""
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(c: _Cand, want_genre: bool) -> None:
        async with sem:
            try:
                c.feat = await _resolve_feat(
                    session, c.artists, c.title,
                    dz_item=c.dz_item, mbid=c.mbid, want_genre=want_genre,
                )
            except Exception:
                c.feat = _new_feat(c.artists, c.title)

    await asyncio.gather(*[one(c, i < ITUNES_CAP) for i, c in enumerate(cands)])
    cands = [c for c in cands if c.feat.get("dz_id") or c.feat.get("it_id")]

    # AcousticBrainz — bitta batch'da barcha MBID'lar (seed ham)
    need_ab = [f for f in [seed] + [c.feat for c in cands]
               if f.get("mbid") and f.get("ab") is None and _stale(f, "ab")]
    if need_ab:
        ab_map = await _ab_batch(session, [f["mbid"] for f in need_ab])
        for f in need_ab:
            f["ab"] = ab_map.get(f["mbid"]) or None
            _mark(f, "ab")
            await _save_feat(f)

    # Last.fm teglari — faqat kalit bo'lsa, top kandidatlar uchun
    if key:
        tag_sem = asyncio.Semaphore(CONCURRENCY)

        async def tags_for(f: dict) -> None:
            async with tag_sem:
                if not f.get("tags") and _stale(f, "tags"):
                    f["tags"] = await _fm_track_tags(session, f["artists"], f["title"], key)
                    _mark(f, "tags")
                    await _save_feat(f)

        await asyncio.gather(*[tags_for(c.feat) for c in cands[:TAGS_CAP]])

    # Lokal audio tahlil — seed (majburiy) + eng istiqbolli kandidatlar
    audio_sem = asyncio.Semaphore(AUDIO_CONC)

    async def analyze(f: dict) -> None:
        async with audio_sem:
            if f.get("audio") is not None or not f.get("preview") or not _stale(f, "audio"):
                return
            vec = await audio_analysis.analyze_url(session, f["preview"])
            _mark(f, "audio")
            if vec is not None:
                f["audio"] = vec.to_dict()
            await _save_feat(f)

    targets = [c.feat for c in cands if c.feat.get("preview") and c.feat.get("audio") is None]
    targets = targets[:AUDIO_CAP]
    jobs = [analyze(f) for f in targets]
    if seed.get("preview") and seed.get("audio") is None:
        jobs.append(analyze(seed))
    await asyncio.gather(*jobs)

    return cands


# ─── Ballash ──────────────────────────────────────────────────────────────────

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


def _score(seed: dict, seed_av: AudioVector | None, c: _Cand,
           av_cache: dict[str, AudioVector]) -> float:
    """0..1 — mavjud signallar bo'yicha normallashgan vaznli o'xshashlik."""
    f = c.feat
    parts: list[tuple[float, float]] = []

    # Audio: lokal DSP (asosiy) + AcousticBrainz mood (qo'shimcha)
    cand_av = av_cache.get(c.key)
    if cand_av is None and f.get("audio"):
        cand_av = av_cache[c.key] = AudioVector.from_dict(f["audio"])
    ab = _ab_sim(seed.get("ab"), f.get("ab"))
    if seed_av is not None and cand_av is not None:
        dsp = audio_analysis.similarity(seed_av, cand_av)
        audio_s = 0.75 * dsp + 0.25 * ab if ab is not None else dsp
        parts.append((W_AUDIO, audio_s))
    elif ab is not None:
        parts.append((W_AUDIO * 0.55, ab))  # faqat mood-modellar — zaifroq dalil

    b = c.behavioral
    if b > 0:
        parts.append((W_BEHAV, b))

    if seed.get("tags") and f.get("tags"):
        parts.append((W_TAGS, _cosine(seed["tags"], f["tags"])))

    sg, cg = _genre_tokens(seed.get("genre") or ""), _genre_tokens(f.get("genre") or "")
    if sg and cg:
        parts.append((W_GENRE, len(sg & cg) / len(sg | cg)))

    try:
        sy, cy = int(seed.get("year") or 0), int(f.get("year") or 0)
    except ValueError:
        sy = cy = 0
    if sy and cy:
        parts.append((W_ERA, math.exp(-(((sy - cy) / 9.0) ** 2))))

    sd, cd = int(seed.get("duration") or 0), int(f.get("duration") or 0)
    if sd and cd:
        parts.append((W_DUR, math.exp(-(((sd - cd) / 90.0) ** 2))))

    if not parts:
        return 0.0
    wsum = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / wsum
    if wsum < 0.35:  # dalil kam — ehtiyotkor pasaytirish
        score *= 0.85
    return score


def _timbre_cos(a: AudioVector | None, b: AudioVector | None) -> float:
    if a is None or b is None or not a.mel or not b.mel:
        return 0.0
    dot = sum(x * y for x, y in zip(a.mel, b.mel))
    return max(0.0, dot)  # vektorlar L2=1


# ─── Tanlash: MMR + cheklovlar + rotatsiya ────────────────────────────────────

def _select(
    seed: dict, cands: list[_Cand], limit: int,
    shown: set[str], seed_artist_norm: str, rng: random.Random,
) -> list[tuple[_Cand, float]]:
    seed_av = AudioVector.from_dict(seed["audio"]) if seed.get("audio") else None
    av_cache: dict[str, AudioVector] = {}

    seed_title = seed.get("title") or ""
    rel: dict[str, float] = {}
    for c in cands:
        s = _score(seed, seed_av, c, av_cache)
        if c.key in shown:
            s -= ROT_PENALTY
        rank = int(c.feat.get("rank") or 0)
        if 0 < rank < 200_000:
            s += GEM_BONUS  # discovery: kam-mashhur, lekin mos treklar
        if _VERSION_PEN.search(c.title) and not _VERSION_PEN.search(seed_title):
            s -= 0.06  # live/remaster/demo — studiya versiyasi afzal
        s += rng.uniform(0.0, 0.015)  # mayda jitter — teng ballar har safar boshqacha
        rel[c.key] = s

    pool = sorted(cands, key=lambda c: rel[c.key], reverse=True)

    out: list[tuple[_Cand, float]] = []
    artist_count: dict[str, int] = {}
    picked_titles: set[str] = set()
    floor = SCORE_FLOOR

    while len(out) < limit and pool:
        best, best_v = None, -1e9
        for c in pool:
            a = _norm(c.artists)
            cap = SEED_ARTIST_CAP if a == seed_artist_norm else PER_ARTIST_CAP
            if artist_count.get(a, 0) >= cap:
                continue
            if _base_title(c.title) in picked_titles:  # boshqa ijrochidagi cover/duplikat
                continue
            # MMR: tanlanganlarga ortiqcha o'xshash bo'lsa jarima
            red = 0.0
            for p, _ in out:
                r = 0.55 * (a == _norm(p.artists))
                r += 0.30 * _timbre_cos(av_cache.get(c.key), av_cache.get(p.key))
                r += 0.15 * _cosine(c.feat.get("tags") or {}, p.feat.get("tags") or {})
                red = max(red, r)
            v = rel[c.key] - MMR_LAMBDA * red
            if v > best_v:
                best, best_v = c, v

        if best is None:
            break
        pool.remove(best)
        score = rel[best.key]
        if score < floor:
            if len(out) >= 10:
                break
            floor = max(0.15, floor - 0.05)  # kam natija — chegara yumshaydi
        a = _norm(best.artists)
        artist_count[a] = artist_count.get(a, 0) + 1
        picked_titles.add(_base_title(best.title))
        out.append((best, max(0.0, min(1.0, score))))

    return out


# ─── Hovuz keshi (takroriy bosishlar uchun) ───────────────────────────────────

_pool_cache: OrderedDict[str, tuple[float, dict, list[_Cand]]] = OrderedDict()
_POOL_MAX = 32


def _pool_get(seed_key: str):
    hit = _pool_cache.get(seed_key)
    if hit and time.monotonic() - hit[0] < POOL_TTL:
        return hit[1], hit[2]
    return None


def _pool_put(seed_key: str, seed: dict, cands: list[_Cand]) -> None:
    _pool_cache[seed_key] = (time.monotonic(), seed, cands)
    _pool_cache.move_to_end(seed_key)
    while len(_pool_cache) > _POOL_MAX:
        _pool_cache.popitem(last=False)


# ─── Fallback: seed'ga bog'langan zaxira yo'llar ──────────────────────────────

async def _fallback(session, artist: str, title: str, seed: dict, limit: int,
                    user_id: int, seed_key: str) -> list[Track]:
    """LB/Last.fm natija bermasa: Deezer artist-radio/related (seed'ga bog'liq!),
    u ham bo'lmasa — seed-shartli matn qidiruvi. Hech qachon global ro'yxat emas."""
    cands: list[_Cand] = []

    if seed.get("dz_artist_id"):
        radio, related = await asyncio.gather(
            _dz_artist_radio(session, seed["dz_artist_id"], 30),
            _dz_related_artists(session, seed["dz_artist_id"], 6),
            return_exceptions=True,
        )
        items = list(radio) if isinstance(radio, list) else []
        rel_ids = [int(r.get("id") or 0) for r in (related if isinstance(related, list) else [])]
        tops = await asyncio.gather(
            *[_dz_artist_top(session, rid, 4) for rid in rel_ids if rid],
            return_exceptions=True,
        )
        for lst in tops:
            items += lst if isinstance(lst, list) else []

        seen: set[str] = set()
        for it in items:
            a = (it.get("artist") or {}).get("name") or ""
            ti = it.get("title") or ""
            k = _feat_key(a, ti)
            if not a or not ti or k == seed_key or k in seen or _is_junk(ti, title):
                continue
            seen.add(k)
            c = _Cand(artists=a, title=ti, key=k, sources={"radio"}, dz_item=it)
            cands.append(c)

    if cands:
        cands = await _enrich(session, seed, cands[:ENRICH_CAP], key="")
        shown = await _get_shown(user_id, seed_key)
        rng = random.Random(f"{seed_key}|{int(time.time() // 86400)}|{len(shown)}")
        picks = _select(seed, cands, limit, shown, _norm(artist), rng)
        tracks = [t for c, s in picks if (t := _feat_track(c.feat, s))]
        if tracks:
            await _mark_shown(user_id, seed_key, [c.key for c, _ in picks])
            return tracks

    # Oxirgi chora: seed-shartli matn qidiruvi (janr/global emas!)
    from bot.services import search_engine

    queries = [f"{artist} {title} similar songs", f"songs like {artist} {title}"]
    if seed.get("genre"):
        queries.append(f"{seed['genre']} {seed.get('year','')} songs".strip())
    batches = await asyncio.gather(*[search_engine.search(q) for q in queries], return_exceptions=True)
    seen2: set[str] = {seed_key}
    artist_count: dict[str, int] = {}
    out: list[Track] = []
    for batch in batches:
        for tr in batch if isinstance(batch, list) else []:
            k = _feat_key(tr.artists, tr.title)
            if k in seen2 or _base_title(tr.title) == _base_title(title):
                continue
            a = _norm(tr.artists)
            if artist_count.get(a, 0) >= PER_ARTIST_CAP + 1:  # matn qidiruvda biroz yumshoqroq
                continue
            seen2.add(k)
            artist_count[a] = artist_count.get(a, 0) + 1
            out.append(tr)
    return out[:limit]


# ─── Rotatsiya xotirasi ───────────────────────────────────────────────────────

async def _get_shown(user_id: int, seed_key: str) -> set[str]:
    from bot.db import repo

    try:
        return await repo.rec_shown_get(user_id, seed_key, time.time() - SHOWN_DAYS * 86400)
    except Exception:
        return set()


async def _mark_shown(user_id: int, seed_key: str, keys: list[str]) -> None:
    from bot.db import repo

    try:
        await repo.rec_shown_add(user_id, seed_key, keys)
    except Exception:
        log.debug("rec_shown yozishda xato", exc_info=True)


# ─── Ommaviy interfeys ────────────────────────────────────────────────────────

async def get_similar(track: Track, limit: int = 18, user_id: int = 0) -> list[Track]:
    """`track`ga OVOZI jihatidan o'xshash treklar (10-18 ta).

    Har chaqiriqda rotatsiya tufayli biroz boshqacha ro'yxat qaytadi.
    Natijalar to'g'ridan-to'g'ri store.remember() + keyboards.search_results()
    ga uzatishga tayyor (sim maydonida haqiqiy o'xshashlik bali).
    """
    from bot.config import settings

    key = settings.lastfm_api_key
    artist, title = _seed_names(track)
    seed_key = _feat_key(artist, title)
    session = await spotify.session()

    try:
        pooled = _pool_get(seed_key)
        if pooled is not None:
            seed, cands = pooled
        else:
            # 1) Seed identifikatsiyasi (parallel)
            mbid_task = _lb_lookup(session, artist, title)
            feat_task = _resolve_feat(
                session, artist, title, want_detail=True, want_genre=True,
            )
            (mbid, artist_mbids), seed = await asyncio.gather(mbid_task, feat_task)
            if mbid and not seed.get("mbid"):
                seed["mbid"] = mbid
                await _save_feat(seed)
            seed["artist_mbids"] = artist_mbids  # faqat shu run uchun (keshga yozilmaydi)
            if key and not seed.get("tags"):
                seed["tags"] = await _fm_track_tags(session, artist, title, key)
                await _save_feat(seed)

            # 2) Kandidatlar 3) dedup/filtr
            raw = await _generate(session, seed, artist, title, key)
            if not raw:
                return await _fallback(session, artist, title, seed, limit, user_id, seed_key)

            # 4-5) Boyitish + audio
            cands = await _enrich(session, seed, _interleave(raw, ENRICH_CAP), key)
            if not cands:
                return await _fallback(session, artist, title, seed, limit, user_id, seed_key)
            _pool_put(seed_key, seed, cands)

        # 6-8) Ballash, MMR, rotatsiya, sifat darvozasi
        shown = await _get_shown(user_id, seed_key)
        rng = random.Random(f"{seed_key}|{int(time.time() // 86400)}|{len(shown)}")
        picks = _select(seed, cands, limit, shown, _norm(artist), rng)
        tracks = [t for c, s in picks if (t := _feat_track(c.feat, s))]

        if len(tracks) < 6:
            extra = await _fallback(session, artist, title, seed, limit - len(tracks), user_id, seed_key)
            have = {_feat_key(t.artists, t.title) for t in tracks}
            tracks += [t for t in extra if _feat_key(t.artists, t.title) not in have]

        if tracks:
            tracks.sort(key=lambda t: t.sim, reverse=True)
            await _mark_shown(user_id, seed_key, [c.key for c, _ in picks])
            log.info(
                "similar: %r → %d ta (mbid=%s, audio=%s)",
                f"{artist} - {title}", len(tracks),
                "bor" if seed.get("mbid") else "yo'q",
                "bor" if seed.get("audio") else "yo'q",
            )
            return tracks[:limit]
    except Exception:
        log.exception("Tavsiya dvigateli xatosi %r", track.title)

    try:
        seed = await _load_feat(artist, title)
        return await _fallback(session, artist, title, seed, limit, user_id, seed_key)
    except Exception:
        log.exception("Fallback ham xato %r", track.title)
        return []
