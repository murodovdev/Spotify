"""Qisqa muddatli in-memory saqlash: qidiruv natijalari va tasdiq kutayotgan to'plamlar."""

import secrets
from collections import OrderedDict

from bot.services.spotify import Track

_MAX = 300


class _Store(OrderedDict):
    def put(self, value) -> str:
        token = secrets.token_hex(4)
        self[token] = value
        while len(self) > _MAX:
            self.popitem(last=False)
        return token


# token -> (query, [Track])
searches: _Store = _Store()

# token -> (user_id, title, [Track])
pending_collections: _Store = _Store()


def stash_search(query: str, tracks: list[Track]) -> str:
    return searches.put((query, tracks))


def stash_collection(user_id: int, title: str, tracks: list[Track]) -> str:
    return pending_collections.put((user_id, title, tracks))


# YouTube qidiruvidan kelgan treklar metadatasi ("yt:<videoId>" -> Track)
yt_tracks: OrderedDict = OrderedDict()


def remember_yt(tracks: list[Track]) -> None:
    for t in tracks:
        if t.id.startswith("yt:"):
            yt_tracks[t.id] = t
    while len(yt_tracks) > _MAX:
        yt_tracks.popitem(last=False)


def get_yt(track_id: str) -> Track | None:
    return yt_tracks.get(track_id)
