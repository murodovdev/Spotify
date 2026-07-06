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
        # Liked Songs — to'liq kenglikda
        kb.row(InlineKeyboardButton(text=t.BTN_LIKED, callback_data="menu:liked"))
        # Sevimlilar + Sozlamalar — 2 ustun
        kb.row(
            InlineKeyboardButton(text=t.BTN_FAVORITES, callback_data="menu:favorites"),
            InlineKeyboardButton(text=t.BTN_SETTINGS, callback_data="menu:settings"),
        )
        # Uzish + Qo'llanma — 2 ustun
        kb.row(
            InlineKeyboardButton(text=t.BTN_DISCONNECT, callback_data="menu:disconnect"),
            InlineKeyboardButton(text=t.BTN_HELP, callback_data="menu:help"),
        )
    else:
        # Ulash — to'liq kenglikda
        kb.row(InlineKeyboardButton(text=t.BTN_CONNECT, callback_data="menu:connect"))
        # Sevimlilar + Sozlamalar — 2 ustun
        kb.row(
            InlineKeyboardButton(text=t.BTN_FAVORITES, callback_data="menu:favorites"),
            InlineKeyboardButton(text=t.BTN_SETTINGS, callback_data="menu:settings"),
        )
        # Qo'llanma — to'liq kenglikda
        kb.row(InlineKeyboardButton(text=t.BTN_HELP, callback_data="menu:help"))
    return kb.as_markup()


def track_buttons(track, t: Texts, is_fav: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    # Spotify ochish + Sevimlilar
    if track.id.startswith("yt:"):
        kb.row(
            InlineKeyboardButton(text="▶️ YouTube Music", url=track.url),
            InlineKeyboardButton(
                text=t.BTN_FAV_SAVED if is_fav else t.BTN_FAV_ADD,
                callback_data=f"fav:{track.id}",
            ),
        )
    else:
        kb.row(
            InlineKeyboardButton(text=t.BTN_OPEN, url=track.url),
            InlineKeyboardButton(
                text=t.BTN_FAV_SAVED if is_fav else t.BTN_FAV_ADD,
                callback_data=f"fav:{track.id}",
            ),
        )
    # Albom + Ijrochi (mavjud bo'lsa)
    extras = []
    if track.album_id:
        extras.append(InlineKeyboardButton(text=t.BTN_ALBUM, callback_data=f"dl:a:{track.album_id}"))
    if track.artist_id:
        extras.append(InlineKeyboardButton(text=t.BTN_ARTIST, callback_data=f"dl:ar:{track.artist_id}"))
    if extras:
        kb.row(*extras)
    return kb.as_markup()


def favorites_list(rows, t: Texts) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in rows:
        title = r["title"] or ""
        artist = r["artist"] or ""
        label = f"{artist} — {title}" if artist else title
        label = label.strip(" —") or "🎵"
        if len(label) > 55:
            label = label[:54] + "…"
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
        label = f"{tr.artists} — {tr.title}".strip(" —") or "🎵"
        if len(label) > 48:
            label = label[:47] + "…"
        kb.button(
            text=f"🎵 {label}  ·  {mins}:{secs:02d}",
            callback_data=f"dl:t:{tr.id}",
        )
    kb.adjust(1)

    pages = (len(tracks) + per_page - 1) // per_page
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text=t.BTN_PREV, callback_data=f"sr:{token}:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text=t.BTN_NEXT, callback_data=f"sr:{token}:{page + 1}"))
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
        icon = "✅" if q == quality else "◻️"
        label = "🔉 128 kbps" if q == "128" else "🔊 320 kbps"
        return f"{icon} {label}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=qlabel("128"), callback_data="q:128"),
                InlineKeyboardButton(text=qlabel("320"), callback_data="q:320"),
            ],
            [
                InlineKeyboardButton(text=t.BTN_LANG, callback_data="menu:lang"),
            ],
            [
                InlineKeyboardButton(text=t.BTN_BACK, callback_data="menu:home"),
            ],
        ]
    )


def playlist_browser(
    token: str,
    tracks,
    page: int,
    t: Texts,
    per_page: int = 12,
    sort_pop: bool = False,
    has_pop: bool = False,
) -> InlineKeyboardMarkup:
    """Interaktiv playlist: sahifalangan qo'shiq tugmalari + boshqaruv."""
    kb = InlineKeyboardBuilder()
    pages = max(1, (len(tracks) + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    start = page * per_page
    for tr in tracks[start : start + per_page]:
        star = "⭐ " if sort_pop and tr.popularity else ""
        label = f"{tr.artists} — {tr.title}".strip(" —") or "🎵"
        if len(label) > 48:
            label = label[:47] + "…"
        if tr.duration:
            mins, secs = divmod(tr.duration, 60)
            label = f"{label}  ·  {mins}:{secs:02d}"
        kb.button(text=f"🎵 {star}{label}", callback_data=f"dl:t:{tr.id}")
    kb.adjust(1)

    s = 1 if sort_pop else 0
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text=t.BTN_PREV, callback_data=f"pl:p:{token}:{page - 1}:{s}"
                )
            )
        nav.append(
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="pl:nop")
        )
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text=t.BTN_NEXT, callback_data=f"pl:p:{token}:{page + 1}:{s}"
                )
            )
        kb.row(*nav)

    controls = [
        InlineKeyboardButton(text=t.BTN_PL_SHUFFLE, callback_data=f"pl:sh:{token}"),
        InlineKeyboardButton(text=t.BTN_PL_SEARCH, callback_data=f"pl:s:{token}"),
    ]
    if has_pop:
        pop_label = f"{t.BTN_PL_POPULAR} ✓" if sort_pop else t.BTN_PL_POPULAR
        controls.append(
            InlineKeyboardButton(text=pop_label, callback_data=f"pl:p:{token}:0:{1 - s}")
        )
    kb.row(*controls)
    kb.row(InlineKeyboardButton(text=t.BTN_PL_CLOSE, callback_data="pl:x"))
    return kb.as_markup()
