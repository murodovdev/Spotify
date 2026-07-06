"""Spotify metadata klienti.

Ikki rejim:
- Rasmiy Web API (client credentials) — to'liq imkoniyat, app egasida Premium talab qilinadi.
- Embed fallback — open.spotify.com/embed sahifalaridan metadata, kalitlarsiz ham ishlaydi.
  API 401/403 qaytarsa avtomatik shu rejimga o'tiladi. Cheklovlar: playlist ~50 trek,
  matn qidiruv YouTube Music orqali bajariladi, Liked Songs esa faqat rasmiy API'da ishlaydi.
"""

import asyncio
import base64
import json
import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import aiohttp

from bot.config import settings
from bot.db import repo
from bot.security import decrypt, encrypt

log = logging.getLogger(__name__)

API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTH_URL = "https://accounts.spotify.com/authorize"
SCOPES = "user-library-read playlist-read-private"

EMBED_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


class SpotifyError(Exception):
    pass


class NotConnected(Exception):
    """Foydalanuvchi Spotify hisobini hali ulamagan."""


@dataclass(slots=True)
class Track:
    id: str
    title: str
    artists: str
    artist_id: str
    album: str
    album_id: str
    duration: int  # soniyalarda
    cover_url: str
    thumb_url: str
    year: str
    track_no: int
    popularity: int = 0
    video_id: str = ""  # YouTube qidiruvidan kelgan treklar uchun
    genre: str = ""  # metadata provayderlaridan (iTunes) — mavjud bo'lsa

    @property
    def full_name(self) -> str:
        return f"{self.artists} — {self.title}"

    @property
    def url(self) -> str:
        if self.id.startswith("yt:"):
            return f"https://music.youtube.com/watch?v={self.video_id or self.id[3:]}"
        return f"https://open.spotify.com/track/{self.id}"


# --- Rasmiy API javobini parslash ---

def _parse_track(t: dict, album: dict | None = None) -> Track:
    album = album or t.get("album") or {}
    images = album.get("images") or []
    cover = images[0]["url"] if images else ""
    thumb = images[1]["url"] if len(images) > 1 else cover
    artists = t.get("artists") or []
    return Track(
        id=t["id"],
        title=t.get("name", ""),
        artists=", ".join(a["name"] for a in artists),
        artist_id=(artists[0].get("id") or "") if artists else "",
        album=album.get("name", ""),
        album_id=album.get("id") or "",
        duration=round((t.get("duration_ms") or 0) / 1000),
        cover_url=cover,
        thumb_url=thumb,
        year=(album.get("release_date") or "")[:4],
        track_no=t.get("track_number") or 0,
        popularity=t.get("popularity") or 0,
    )


@dataclass(slots=True)
class Playlist:
    title: str
    creator: str
    total: int
    cover_url: str
    tracks: list[Track]


# --- Embed sahifasini parslash ---

def _embed_images(entity: dict) -> tuple[str, str]:
    images = (entity.get("visualIdentity") or {}).get("image") or []
    by_size = sorted(images, key=lambda i: i.get("maxWidth", 0))
    if not by_size:
        return "", ""
    cover = by_size[-1]["url"]
    thumb = next((i["url"] for i in by_size if i.get("maxWidth", 0) >= 300), cover)
    return cover, thumb


def _embed_year(entity: dict) -> str:
    iso = (entity.get("releaseDate") or {}).get("isoString") or ""
    return iso[:4]


def _parse_embed_track(e: dict) -> Track:
    artists = e.get("artists") or []
    cover, thumb = _embed_images(e)
    artist_uri = (artists[0].get("uri") or "") if artists else ""
    return Track(
        id=e.get("id") or e["uri"].split(":")[-1],
        title=e.get("name") or e.get("title") or "",
        artists=", ".join(a.get("name", "") for a in artists),
        artist_id=artist_uri.split(":")[-1] if artist_uri else "",
        album="",
        album_id="",
        duration=round((e.get("duration") or 0) / 1000),
        cover_url=cover,
        thumb_url=thumb,
        year=_embed_year(e),
        track_no=0,
    )


def _parse_embed_item(
    item: dict, album: str = "", cover: str = "", thumb: str = "", year: str = "", no: int = 0
) -> Track:
    return Track(
        id=item["uri"].split(":")[-1],
        title=item.get("title", ""),
        artists=item.get("subtitle", ""),
        artist_id="",
        album=album,
        album_id="",
        duration=round((item.get("duration") or 0) / 1000),
        cover_url=cover,
        thumb_url=thumb,
        year=year,
        track_no=no,
    )


class SpotifyClient:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._app_token: str = ""
        self._app_token_exp: float = 0
        self._lock = asyncio.Lock()
        self._embed_mode = False  # API rad etsa True bo'ladi va shunday qoladi

    @property
    def has_credentials(self) -> bool:
        return bool(settings.spotify_client_id and settings.spotify_client_secret)

    @property
    def api_mode(self) -> bool:
        """Rasmiy Web API ishlayotgan bo'lsa True (embed fallback'ga o'tmagan)."""
        return self.has_credentials and not self._embed_mode

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=30,
                limit_per_host=10,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                keepalive_timeout=30,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # --- Tokenlar ---

    def _basic_auth(self) -> str:
        raw = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
        return "Basic " + base64.b64encode(raw.encode()).decode()

    async def _token_request(self, data: dict) -> dict:
        session = await self.session()
        async with session.post(
            TOKEN_URL, data=data, headers={"Authorization": self._basic_auth()}
        ) as resp:
            body = await resp.json()
            if resp.status != 200:
                raise SpotifyError(f"Token so'rovi xatosi {resp.status}: {body}")
            return body

    async def _app_access_token(self) -> str:
        async with self._lock:
            if self._app_token and time.time() < self._app_token_exp - 60:
                return self._app_token
            data = await self._token_request({"grant_type": "client_credentials"})
            self._app_token = data["access_token"]
            self._app_token_exp = time.time() + data.get("expires_in", 3600)
            return self._app_token

    # --- OAuth (foydalanuvchi hisobi) ---

    def auth_url(self, state: str) -> str:
        params = {
            "client_id": settings.spotify_client_id,
            "response_type": "code",
            "redirect_uri": settings.redirect_uri,
            "scope": SCOPES,
            "state": state,
            "show_dialog": "false",
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, user_id: int) -> None:
        data = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.redirect_uri,
            }
        )
        await repo.save_tokens(
            user_id,
            encrypt(data["refresh_token"]),
            encrypt(data["access_token"]),
            time.time() + data.get("expires_in", 3600),
        )

    async def _user_access_token(self, user_id: int) -> str:
        row = await repo.get_tokens(user_id)
        if row is None:
            raise NotConnected
        if row["access_token"] and row["expires_at"] > time.time() + 60:
            return decrypt(row["access_token"])
        refresh = decrypt(row["refresh_token"])
        data = await self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh}
        )
        access = data["access_token"]
        new_refresh = data.get("refresh_token") or refresh
        await repo.save_tokens(
            user_id,
            encrypt(new_refresh),
            encrypt(access),
            time.time() + data.get("expires_in", 3600),
        )
        return access

    # --- HTTP ---

    async def _get(self, url: str, params: dict | None = None, token: str | None = None) -> dict:
        session = await self.session()
        backoff = 1.0
        for attempt in range(4):
            tok = token or await self._app_access_token()
            try:
                async with session.get(
                    url, params=params, headers={"Authorization": f"Bearer {tok}"}
                ) as resp:
                    if resp.status == 429:
                        retry = float(resp.headers.get("Retry-After", backoff))
                        await asyncio.sleep(min(retry, 20))
                        backoff = min(backoff * 2, 16)
                        continue
                    if resp.status >= 500:
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 16)
                        continue
                    if resp.status != 200:
                        raise SpotifyError(f"Spotify API {resp.status}: {await resp.text()}")
                    return await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == 3:
                    raise
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 16)
        raise SpotifyError("Spotify API: juda ko'p urinish (rate limit)")

    async def _embed_entity(self, kind: str, sid: str) -> dict:
        session = await self.session()
        url = f"https://open.spotify.com/embed/{kind}/{sid}"
        async with session.get(url, headers={"User-Agent": EMBED_UA}) as resp:
            if resp.status != 200:
                raise SpotifyError(f"Embed sahifasi {resp.status}: {url}")
            page = await resp.text()
        m = _NEXT_DATA_RE.search(page)
        if not m:
            raise SpotifyError("Embed sahifasidan ma'lumot o'qib bo'lmadi")
        try:
            return json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            raise SpotifyError("Embed JSON tuzilishi o'zgargan") from e

    async def _call(self, api_fn, embed_fn):
        """Rasmiy API'ni sinaydi; 401/403 bo'lsa butunlay embed rejimga o'tadi."""
        if self._embed_mode or not self.has_credentials:
            return await embed_fn()
        try:
            return await api_fn()
        except SpotifyError as e:
            msg = str(e)
            if "API 403" in msg or "API 401" in msg or "Token so'rovi xatosi" in msg:
                log.warning("Rasmiy Spotify API rad etdi — embed rejimga o'tildi: %s", msg[:200])
                self._embed_mode = True
                return await embed_fn()
            raise

    # --- Metadata (ikkala rejim) ---

    async def track(self, track_id: str) -> Track:
        async def api():
            return _parse_track(await self._get(f"{API}/tracks/{track_id}"))

        async def emb():
            return _parse_embed_track(await self._embed_entity("track", track_id))

        return await self._call(api, emb)

    async def album(self, album_id: str) -> tuple[str, list[Track]]:
        async def api():
            data = await self._get(f"{API}/albums/{album_id}")
            tracks = [
                _parse_track(t, album=data)
                for t in data["tracks"]["items"]
                if t.get("id")
            ]
            next_url = data["tracks"].get("next")
            while next_url:
                page = await self._get(next_url)
                tracks += [_parse_track(t, album=data) for t in page["items"] if t.get("id")]
                next_url = page.get("next")
            return data["name"], tracks

        async def emb():
            e = await self._embed_entity("album", album_id)
            cover, thumb = _embed_images(e)
            year = _embed_year(e)
            name = e.get("name") or e.get("title") or ""
            tracks = [
                _parse_embed_item(item, album=name, cover=cover, thumb=thumb, year=year, no=i)
                for i, item in enumerate(e.get("trackList") or [], start=1)
                if item.get("uri")
            ]
            return name, tracks

        return await self._call(api, emb)

    async def playlist(self, playlist_id: str) -> tuple[str, list[Track]]:
        async def api():
            meta = await self._get(
                f"{API}/playlists/{playlist_id}", params={"fields": "name"}
            )
            tracks: list[Track] = []
            url: str | None = f"{API}/playlists/{playlist_id}/tracks"
            params = {"limit": 100}
            while url:
                page = await self._get(url, params=params)
                params = None
                for item in page.get("items", []):
                    t = item.get("track")
                    if t and t.get("id") and t.get("type", "track") == "track":
                        tracks.append(_parse_track(t))
                url = page.get("next")
            return meta["name"], tracks

        async def emb():
            e = await self._embed_entity("playlist", playlist_id)
            name = e.get("name") or e.get("title") or ""
            tracks = [
                _parse_embed_item(item)
                for item in e.get("trackList") or []
                if item.get("uri")
            ]
            return name, tracks

        return await self._call(api, emb)

    async def playlist_info(self, playlist_id: str) -> Playlist:
        """Playlist metadatasi + treklar — interaktiv brauzer uchun.

        Nomi, egasi, muqovasi va to'liq trek ro'yxatini qaytaradi.
        """
        async def api():
            meta = await self._get(
                f"{API}/playlists/{playlist_id}",
                params={"fields": "name,owner(display_name),images"},
            )
            images = meta.get("images") or []
            cover = images[0]["url"] if images else ""
            tracks: list[Track] = []
            url: str | None = f"{API}/playlists/{playlist_id}/tracks"
            params = {"limit": 100}
            while url:
                page = await self._get(url, params=params)
                params = None
                for item in page.get("items", []):
                    t = item.get("track")
                    if t and t.get("id") and t.get("type", "track") == "track":
                        tracks.append(_parse_track(t))
                url = page.get("next")
            return Playlist(
                title=meta.get("name", ""),
                creator=(meta.get("owner") or {}).get("display_name") or "",
                total=len(tracks),
                cover_url=cover,
                tracks=tracks,
            )

        async def emb():
            e = await self._embed_entity("playlist", playlist_id)
            cover, _ = _embed_images(e)
            tracks = [
                _parse_embed_item(item)
                for item in e.get("trackList") or []
                if item.get("uri")
            ]
            return Playlist(
                title=e.get("name") or e.get("title") or "",
                creator=e.get("subtitle") or "",
                total=len(tracks),
                cover_url=cover,
                tracks=tracks,
            )

        return await self._call(api, emb)

    async def artist_top(self, artist_id: str) -> tuple[str, list[Track]]:
        async def api():
            artist = await self._get(f"{API}/artists/{artist_id}")
            data = await self._get(
                f"{API}/artists/{artist_id}/top-tracks", params={"market": "US"}
            )
            tracks = [_parse_track(t) for t in data.get("tracks", []) if t.get("id")]
            return artist["name"], tracks

        async def emb():
            e = await self._embed_entity("artist", artist_id)
            name = e.get("name") or e.get("title") or ""
            tracks = [
                _parse_embed_item(item)
                for item in e.get("trackList") or []
                if item.get("uri")
            ]
            return name, tracks

        return await self._call(api, emb)

    async def search(self, query: str, limit: int = 24) -> list[Track]:
        async def api():
            data = await self._get(
                f"{API}/search",
                params={"q": query, "type": "track", "limit": min(limit, 50)},
            )
            items = data.get("tracks", {}).get("items", [])
            return [_parse_track(t) for t in items if t and t.get("id")]

        async def emb():
            # Embed rejimda qidiruv YouTube Music orqali bajariladi
            from bot.services import matcher

            return await matcher.yt_search(query, limit)

        return await self._call(api, emb)

    async def oembed_thumb(self, track_id: str) -> str:
        """Muqovasiz treklar uchun ochiq oEmbed'dan rasm URL (300px)."""
        try:
            session = await self.session()
            async with session.get(
                "https://open.spotify.com/oembed",
                params={"url": f"https://open.spotify.com/track/{track_id}"},
            ) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("thumbnail_url") or ""
        except Exception:
            pass
        return ""

    # --- Liked Songs (faqat rasmiy API) ---

    async def liked_count(self, user_id: int) -> int:
        token = await self._user_access_token(user_id)
        data = await self._get(f"{API}/me/tracks", params={"limit": 1}, token=token)
        return data.get("total", 0)

    async def liked_tracks(self, user_id: int) -> list[Track]:
        token = await self._user_access_token(user_id)
        tracks: list[Track] = []
        url: str | None = f"{API}/me/tracks"
        params = {"limit": 50}
        while url:
            page = await self._get(url, params=params, token=token)
            params = None
            for item in page.get("items", []):
                t = item.get("track")
                if t and t.get("id"):
                    tracks.append(_parse_track(t))
            url = page.get("next")
        return tracks


spotify = SpotifyClient()
