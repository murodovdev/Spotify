from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts


def main_menu(connected: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if connected:
        kb.button(text=texts.BTN_LIKED, callback_data="menu:liked")
        kb.button(text=texts.BTN_DISCONNECT, callback_data="menu:disconnect")
    else:
        kb.button(text=texts.BTN_CONNECT, callback_data="menu:connect")
        kb.button(text=texts.BTN_LIKED, callback_data="menu:liked")
    kb.button(text=texts.BTN_SETTINGS, callback_data="menu:settings")
    kb.button(text=texts.BTN_HISTORY, callback_data="menu:history")
    kb.button(text=texts.BTN_HELP, callback_data="menu:help")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def track_buttons(track) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if track.album_id:
        kb.button(text=texts.BTN_ALBUM, callback_data=f"dl:a:{track.album_id}")
    if track.artist_id:
        kb.button(text=texts.BTN_ARTIST, callback_data=f"dl:ar:{track.artist_id}")
    kb.button(text=texts.BTN_SPOTIFY, url=track.url)
    kb.adjust(2, 1)
    return kb.as_markup()


def connect_button(auth_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.BTN_CONNECT_URL, url=auth_url)]
        ]
    )


def search_results(tracks, token: str, page: int, per_page: int = 8) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    start = page * per_page
    for t in tracks[start : start + per_page]:
        mins, secs = divmod(t.duration, 60)
        kb.button(
            text=f"🎵 {t.artists} — {t.title} ({mins}:{secs:02d})",
            callback_data=f"dl:t:{t.id}",
        )
    kb.adjust(1)

    pages = (len(tracks) + per_page - 1) // per_page
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text=texts.BTN_PREV, callback_data=f"sr:{token}:{page - 1}")
            )
        nav.append(
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop")
        )
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(text=texts.BTN_NEXT, callback_data=f"sr:{token}:{page + 1}")
            )
        kb.row(*nav)
    return kb.as_markup()


def confirm_collection(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.BTN_START_DL, callback_data=f"go:{token}"),
                InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=f"no:{token}"),
            ]
        ]
    )


def cancel_button(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=f"stop:{user_id}")]
        ]
    )


def settings_kb(quality: str) -> InlineKeyboardMarkup:
    def label(q: str) -> str:
        return f"{'✅ ' if q == quality else ''}{q} kbps"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label("128"), callback_data="q:128"),
                InlineKeyboardButton(text=label("320"), callback_data="q:320"),
            ]
        ]
    )


def history_kb(items) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for row in items:
        kb.button(
            text=f"🎵 {row['artist']} — {row['title']}",
            callback_data=f"dl:t:{row['spotify_id']}",
        )
    kb.adjust(1)
    return kb.as_markup()
