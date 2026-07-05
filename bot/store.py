"""Qisqa muddatli in-memory saqlash: qidiruv natijalari va tasdiq kutayotgan to'plamlar.

Memory budget: ~200 entries per store, each entry ≈ 5-50 KB depending on track count.
Worst case: 200 * 50 KB * 3 stores ≈ 30 MB.
"""

import secrets
from dataclasses import dataclass
from collections import OrderedDict

from bot.services.spotify import Playlist, Track

_MAX = 200


class _Store(OrderedDict):
    def put(self, value) -> str:
        token = secrets.token_hex(4)
        self[token] = value
        while len(self) > _MAX:
            self.popitem(last=False)
        return token


searches: _Store = _Store()
pending_collections: _Store = _Store()
playlists: _Store = _Store()
pending_playlist_searches: OrderedDict[int, str] = OrderedDict()


@dataclass(slots=True)
class PlaylistSession:
    user_id: int
    title: str
    creator: str
    total: int
    cover_url: str
    tracks: list[Track]
    view_tracks: list[Track]
    mode: str = "all"
    query: str = ""
    message_id: int = 0
    has_cover: bool = False


def stash_search(query: str, tracks: list[Track]) -> str:
    return searches.put((query, tracks))


def stash_collection(user_id: int, title: str, tracks: list[Track]) -> str:
    return pending_collections.put((user_id, title, tracks))


def stash_playlist(user_id: int, playlist: Playlist, tracks: list[Track] | None = None) -> str:
    shown = tracks or playlist.tracks
    remember(playlist.tracks)
    return playlists.put(
        PlaylistSession(
            user_id=user_id,
            title=playlist.title,
            creator=playlist.creator,
            total=playlist.total,
            cover_url=playlist.cover_url,
            tracks=playlist.tracks,
            view_tracks=shown,
        )
    )


def remember_playlist_search(user_id: int, token: str) -> None:
    pending_playlist_searches[user_id] = token
    pending_playlist_searches.move_to_end(user_id)
    while len(pending_playlist_searches) > _MAX:
        pending_playlist_searches.popitem(last=False)


# Qidiruv natijalari — id bo'yicha (yt:, it:, dz: sintetik id'lar). Tanlanganda
# tarmoqqa qayta murojaatsiz trekni tiklash uchun kerak.
_MAX_TRACKS = 600
all_tracks: OrderedDict = OrderedDict()


def remember(tracks: list[Track]) -> None:
    for t in tracks:
        all_tracks[t.id] = t
        all_tracks.move_to_end(t.id)
    while len(all_tracks) > _MAX_TRACKS:
        all_tracks.popitem(last=False)


def get(track_id: str) -> Track | None:
    return all_tracks.get(track_id)
