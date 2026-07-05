from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import LANG_LABELS, Texts


def lang_picker(prefix: str = "lang") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, label in LANG_LABELS.items():
        kb.button(text=label, callback_data=f"{prefix}:{code}")
    kb.adjust(3)
    return kb.as_markup()


def main_menu(connected: bool, t: Texts) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if connected:
        kb.button(text=t.BTN_LIKED, callback_data="menu:liked")
        kb.button(text=t.BTN_DISCONNECT, callback_data="menu:disconnect")
    else:
        kb.button(text=t.BTN_CONNECT, callback_data="menu:connect")
    kb.button(text=t.BTN_FAVORITES, callback_data="menu:favorites")
    kb.button(text=t.BTN_SETTINGS, callback_data="menu:settings")
    kb.adjust(2)
    return kb.as_markup()


def track_buttons(track, t: Texts, is_fav: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    row1 = 0
    # 1-qator: havolada ochish + sevimlilarga saqlash
    if track.id.startswith("yt:"):
        kb.button(text="▶️ YouTube Music", url=track.url)
    else:
        kb.button(text=t.BTN_OPEN, url=track.url)
    row1 += 1
    kb.button(
        text=t.BTN_FAV_SAVED if is_fav else t.BTN_FAV_ADD,
        callback_data=f"fav:{track.id}",
    )
    row1 += 1
    # 2-qator: albom / ijrochi (mavjud bo'lsa)
    row2 = 0
    if track.album_id:
        kb.button(text=t.BTN_ALBUM, callback_data=f"dl:a:{track.album_id}")
        row2 += 1
    if track.artist_id:
        kb.button(text=t.BTN_ARTIST, callback_data=f"dl:ar:{track.artist_id}")
        row2 += 1
    if row2:
        kb.adjust(row1, row2)
    else:
        kb.adjust(row1)
    return kb.as_markup()


def favorites_list(rows, t: Texts) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in rows:
        title = r["title"] or ""
        artist = r["artist"] or ""
        label = f"{artist} — {title}" if artist else title
        label = label.strip(" —") or "🎵"
        if len(label) > 60:
            label = label[:59] + "…"
        kb.button(text=f"🎵 {label}", callback_data=f"dl:t:{r['spotify_id']}")
    kb.adjust(1)
    return kb.as_markup()


def connect_button(auth_url: str, t: Texts) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t.BTN_CONNECT_URL, url=auth_url)]
        ]
    )


def search_results(tracks, token: str, page: int, t: Texts, per_page: int = 6) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    start = page * per_page
    for tr in tracks[start : start + per_page]:
        mins, secs = divmod(tr.duration, 60)
        kb.button(
            text=f"{tr.artists} — {tr.title}  {mins}:{secs:02d}",
            callback_data=f"dl:t:{tr.id}",
        )
    kb.adjust(1)

    pages = (len(tracks) + per_page - 1) // per_page
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text=t.BTN_PREV, callback_data=f"sr:{token}:{page - 1}")
            )
        nav.append(
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop")
        )
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(text=t.BTN_NEXT, callback_data=f"sr:{token}:{page + 1}")
            )
        kb.row(*nav)
    return kb.as_markup()


def _short_button(text: str, limit: int = 58) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _playlist_track_label(track) -> str:
    icon = "⭐" if getattr(track, "popularity", 0) else "🎵"
    title = track.title or "Track"
    artist = f" — {track.artists}" if track.artists else ""
    duration = ""
    if track.duration:
        mins, secs = divmod(track.duration, 60)
        duration = f"  {mins}:{secs:02d}"
    return _short_button(f"{icon} {title}{artist}{duration}")


def playlist_browser(
    tracks,
    token: str,
    page: int,
    pages: int,
    t: Texts,
    per_page: int = 10,
    favorites_mode: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text=t.BTN_PLAYLIST_SEARCH, callback_data=f"pl:{token}:search"),
            InlineKeyboardButton(text=t.BTN_PLAYLIST_SHUFFLE, callback_data=f"pl:{token}:shuffle"),
        ],
        [
            InlineKeyboardButton(
                text=t.BTN_PLAYLIST_ALL if favorites_mode else t.BTN_PLAYLIST_FAVS,
                callback_data=f"pl:{token}:all" if favorites_mode else f"pl:{token}:fav",
            )
        ],
    ]

    start = page * per_page
    for idx, track in enumerate(tracks[start : start + per_page], start=start):
        rows.append(
            [
                InlineKeyboardButton(
                    text=_playlist_track_label(track),
                    callback_data=f"pl:{token}:t:{idx}",
                )
            ]
        )

    if pages > 1:
        nav = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text=t.BTN_PREV, callback_data=f"pl:{token}:p:{page - 1}")
            )
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(text=t.BTN_NEXT, callback_data=f"pl:{token}:p:{page + 1}")
            )
        rows.append(nav)

    rows.append([InlineKeyboardButton(text=t.BTN_BACK, callback_data=f"pl:{token}:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_collection(token: str, t: Texts) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t.BTN_START_DL, callback_data=f"go:{token}"),
                InlineKeyboardButton(text=t.BTN_CANCEL, callback_data=f"no:{token}"),
            ]
        ]
    )


def cancel_button(user_id: int, t: Texts) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t.BTN_CANCEL, callback_data=f"stop:{user_id}")]
        ]
    )


def settings_kb(quality: str, lang: str, t: Texts) -> InlineKeyboardMarkup:
    def qlabel(q: str) -> str:
        icon = "✅" if q == quality else "🔘"
        label = "🔉 128 kbps" if q == "128" else "🔊 320 kbps"
        return f"{icon} {label}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=qlabel("128"), callback_data="q:128"),
                InlineKeyboardButton(text=qlabel("320"), callback_data="q:320"),
            ],
            [
                InlineKeyboardButton(
                    text=f"{t.BTN_LANG} · {LANG_LABELS.get(lang, LANG_LABELS['uz'])}",
                    callback_data="menu:lang",
                ),
            ],
        ]
    )
