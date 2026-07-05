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
