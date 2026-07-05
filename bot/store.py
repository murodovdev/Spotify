"""Qisqa muddatli in-memory saqlash: qidiruv natijalari va tasdiq kutayotgan to'plamlar.

Memory budget: ~200 entries per store, each entry ≈ 5-50 KB depending on track count.
Worst case: 200 * 50 KB * 3 stores ≈ 30 MB.
"""

import secrets
from collections import OrderedDict

from bot.services.spotify import Track

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


def stash_search(query: str, tracks: list[Track]) -> str:
    return searches.put((query, tracks))


def stash_collection(user_id: int, title: str, tracks: list[Track]) -> str:
    return pending_collections.put((user_id, title, tracks))


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
