"""Music similarity engine.

Primary path  — Last.fm track.getSimilar (requires LASTFM_API_KEY in .env).
Fallback path — genre/era-based multi-query search via existing search_engine.
Both paths deduplicate against the original track and merge cleanly into the
Track objects the rest of the bot already understands (it: / dz: / yt:).
"""

import asyncio
import logging
import re
import unicodedata
from difflib import SequenceMatcher

import aiohttp

from bot.services.spotify import Track, spotify

log = logging.getLogger(__name__)

ITUNES_URL = "https://itunes.apple.com/search"
LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=12)

# Genre keyword → 2 diverse search phrases that capture similar-sounding music
_GENRE_QUERIES: dict[str, list[str]] = {
    "pop":          ["popular pop hits playlist", "feel good pop songs"],
    "indie pop":    ["indie pop music hits", "dream pop songs playlist"],
    "synth-pop":    ["synthwave synth-pop hits", "80s synth pop music"],
    "electropop":   ["electropop dance songs", "electronic pop music"],
    "r&b/soul":     ["r&b soul hits playlist", "neo soul music"],
    "r&b":          ["r&b music playlist soul", "smooth r&b songs"],
    "hip-hop/rap":  ["hip hop rap playlist", "rap music hits"],
    "hip-hop":      ["hip hop songs playlist", "rap music hits"],
    "rap":          ["rap music hits playlist", "hip hop songs"],
    "trap":         ["trap music hits", "trap rap songs"],
    "alternative":  ["alternative rock indie music", "alternative songs playlist"],
    "rock":         ["rock music playlist hits", "rock songs classics"],
    "indie rock":   ["indie rock music playlist", "alternative indie songs"],
    "classic rock": ["classic rock anthems hits", "70s 80s rock music"],
    "electronic":   ["electronic music dance hits", "edm songs playlist"],
    "dance":        ["dance music hits playlist", "dance pop songs"],
    "house":        ["house music dance playlist", "electronic house songs"],
    "techno":       ["techno electronic music", "dark techno beats"],
    "country":      ["country music songs playlist", "country pop hits"],
    "jazz":         ["jazz standards classics playlist", "smooth jazz music"],
    "classical":    ["classical music orchestra", "piano classical pieces"],
    "metal":        ["metal music songs playlist", "alternative heavy metal"],
    "reggae":       ["reggae dancehall music playlist", "jamaican reggae songs"],
    "latin":        ["latin pop music hits", "latin songs playlist"],
    "soul":         ["soul music r&b playlist", "neo soul classics"],
    "folk":         ["folk music acoustic songs", "singer songwriter folk"],
    "blues":        ["blues rock music playlist", "blues soul songs"],
    "k-pop":        ["k-pop hits songs playlist", "korean pop music"],
    "funk":         ["funk music groove playlist", "funk soul hits"],
    "gospel":       ["gospel music christian songs", "worship music hits"],
    "ambient":      ["ambient atmospheric music", "chillout ambient songs"],
    "punk":         ["punk rock music playlist", "alternative punk songs"],
    "ska":          ["ska reggae music songs", "ska punk playlist"],
    "disco":        ["disco music hits", "70s disco dance songs"],
    "lo-fi":        ["lo-fi hip hop music", "chill lo-fi beats"],
    "emo":          ["emo music songs", "pop punk emo playlist"],
    "grunge":       ["grunge music songs", "90s alternative rock"],
    "indie":        ["indie music songs playlist", "indie pop rock"],
    "acoustic":     ["acoustic songs playlist", "acoustic singer songwriter"],
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def _base_title(title: str) -> str:
    """Strip version tags like (Remix), [Live], feat. X — for dedup keys."""
    return _norm(re.sub(r"[\(\[\{].*?[\)\]\}]", " ", title or ""))


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


# ─── Last.fm path ─────────────────────────────────────────────────────────────

async def _lastfm_similar(
    artist: str, title: str, api_key: str, limit: int = 25,
) -> list[tuple[str, str, float]]:
    """Call Last.fm track.getSimilar → list of (artist, title, match_score)."""
    try:
        session = await spotify.session()
        params = {
            "method": "track.getSimilar",
            "artist": artist,
            "track": title,
            "api_key": api_key,
            "format": "json",
            "limit": str(limit),
            "autocorrect": "1",
        }
        async with session.get(LASTFM_URL, params=params, timeout=_HTTP_TIMEOUT) as resp:
            if resp.status != 200:
                log.warning("Last.fm returned HTTP %s", resp.status)
                return []
            data = await resp.json(content_type=None)
    except Exception:
        log.warning("Last.fm request failed", exc_info=True)
        return []

    if data.get("error"):
        log.warning("Last.fm error %s: %s", data["error"], data.get("message"))
        return []

    raw = data.get("similartracks", {}).get("track") or []
    out: list[tuple[str, str, float]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        art = item.get("artist")
        if not isinstance(art, dict):
            continue
        out.append((art.get("name") or "", item.get("name") or "", float(item.get("match") or 0.5)))
    return out


async def _itunes_lookup(session: aiohttp.ClientSession, artist: str, title: str) -> Track | None:
    """Return one Track from iTunes matching artist+title, or None."""
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


async def _via_lastfm(track: Track, api_key: str, limit: int) -> list[Track]:
    artist = track.artists or track.title
    pairs = await _lastfm_similar(artist, track.title, api_key, limit + 8)
    if not pairs:
        return []

    session = await spotify.session()
    results = await asyncio.gather(*[_itunes_lookup(session, a, t) for a, t, _ in pairs])

    orig_key = (_norm(track.artists), _base_title(track.title))
    seen: set[tuple[str, str]] = {orig_key}
    out: list[Track] = []
    for r in results:
        if r is None:
            continue
        key = (_norm(r.artists), _base_title(r.title))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out[:limit]


# ─── Fallback: genre / era queries ────────────────────────────────────────────

def _style_queries(track: Track) -> list[str]:
    """Build up to 3 diverse queries based on genre + decade."""
    genre = (track.genre or "").lower().strip()
    year  = (track.year or "")[:4]
    decade = f"{year[:3]}0s" if len(year) == 4 else ""

    queries: list[str] = []

    # 1. Genre-matched style phrases (up to 2)
    for key, phrases in _GENRE_QUERIES.items():
        if key in genre:
            queries.extend(phrases[:2])
            break

    # 2. Genre + era
    if decade:
        if genre:
            queries.append(f"{genre} {decade} songs")
        else:
            queries.append(f"best songs {decade}")

    # 3. Raw genre fallback if nothing matched
    if not queries:
        queries.append(f"{genre} songs playlist" if genre else "popular music hits")

    return queries[:3]


async def _via_fallback(track: Track, limit: int) -> list[Track]:
    from bot.services import search_engine

    queries = _style_queries(track)
    batches = await asyncio.gather(*[search_engine.search(q) for q in queries])

    orig_key = (_norm(track.artists), _base_title(track.title))
    seen: set[tuple[str, str]] = {orig_key}
    out: list[Track] = []
    for batch in batches:
        for tr in batch:
            key = (_norm(tr.artists), _base_title(tr.title))
            if key in seen:
                continue
            seen.add(key)
            out.append(tr)
    return out[:limit]


# ─── Public interface ─────────────────────────────────────────────────────────

async def get_similar(track: Track, limit: int = 20) -> list[Track]:
    """
    Return up to `limit` tracks that are musically similar to `track`.

    Uses Last.fm track.getSimilar when LASTFM_API_KEY is configured (recommended).
    Falls back to genre/era multi-query search otherwise.
    Results are ready to be passed directly to store.remember() + keyboards.search_results().
    """
    from bot.config import settings

    if settings.lastfm_api_key:
        tracks = await _via_lastfm(track, settings.lastfm_api_key, limit)
        if tracks:
            return tracks
        log.info("Last.fm returned no results for %r — using fallback", track.title)

    return await _via_fallback(track, limit)
