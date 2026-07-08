from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, SwitchInlineQueryChosenChat
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import LANG_LABELS, Texts
from bot import store


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
    # Sevimlilar
    kb.row(
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


def yt_formats(video_id: str, formats, t: Texts) -> InlineKeyboardMarkup:
    """YouTube video preview ostidagi format tanlash klaviaturasi (2×2 tarmoq)."""
    labels = {
        "mp3": t.BTN_YT_MP3,
        "m4a": t.BTN_YT_M4A,
        "flac": t.BTN_YT_FLAC,
        "opus": t.BTN_YT_OPUS,
    }
    kb = InlineKeyboardBuilder()
    for fmt in formats:
        kb.button(text=labels[fmt], callback_data=f"ytf:{fmt}:{video_id}")
    kb.adjust(2)
    return kb.as_markup()


def force_sub(chats, t: Texts) -> InlineKeyboardMarkup:
    """Majburiy obuna ekrani: har kanal uchun havola + "Qo'shildim" tugmasi.

    Havolasiz chat (username ham, invite_link ham yo'q) tugma sifatida
    ko'rsatilmaydi — Telegram bo'sh `url` bilan klaviaturani rad etadi.
    """
    from bot.services import forcesub

    kb = InlineKeyboardBuilder()
    for c in chats:
        url = forcesub.chat_url(c)
        if not url:
            continue
        icon = "👥" if c["kind"] == "group" else "📢"
        kb.row(InlineKeyboardButton(text=f"{icon} {c['title'][:40]}", url=url))
    kb.row(InlineKeyboardButton(text=t.BTN_FS_CHECK, callback_data="fs:check"))
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
        meta = f"{mins}:{secs:02d}"
        sim = getattr(tr, "sim", 0.0)
        if sim > 0:
            meta = f"{meta}  ·  {round(sim * 100)}% 🎯"
        kb.button(
            text=f"🎵 {label}  ·  {meta}",
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


def post_download_kb(track, t: Texts, is_fav: bool = False) -> InlineKeyboardMarkup:
    """Full interactive keyboard shown after single-track download."""
    kb = InlineKeyboardBuilder()

    # Row 1: Share (native chat picker) + Save to Favorites
    share_query = store.stash_share(track)
    kb.row(
        InlineKeyboardButton(
            text=t.BTN_SHARE,
            switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
                query=share_query,
                allow_user_chats=True,
                allow_group_chats=True,
                allow_channel_chats=True,
                allow_bot_chats=False,
            ),
        ),
        InlineKeyboardButton(
            text=t.BTN_FAV_SAVED if is_fav else t.BTN_FAV_ADD,
            callback_data=f"fav:{track.id}",
        ),
    )

    # Row 2: Similar Songs + Edit Audio + Edit Info
    #
    # YouTube audiosi ko'pincha musiqa emas (vlog, podkast, sharh). Bunday
    # yozuvlar uchun "O'xshash" ma'nosiz (tavsiya dvigateli sarlavha va ijrochi
    # = kanal nomi bo'yicha qidiradi, axlat qaytaradi), "Ma'lumot" esa albom /
    # janr / yil kabi maydonlarni tahrirlashni taklif qiladi — ular yo'q.
    is_youtube = str(track.id).startswith("yt:")
    row = []
    if not is_youtube:
        row.append(InlineKeyboardButton(text=t.BTN_SIMILAR, callback_data=f"sim:{track.id}"))
    row.append(InlineKeyboardButton(text=t.BTN_EFFECTS, callback_data=f"ea:{track.id}"))
    if not is_youtube:
        row.append(InlineKeyboardButton(text=t.BTN_EDIT_META, callback_data=f"em:{track.id}"))
    kb.row(*row)

    # Row 3: Album (if available)
    if track.album_id:
        kb.row(InlineKeyboardButton(text=t.BTN_ALBUM, callback_data=f"dl:a:{track.album_id}"))

    # Row 4: Artist (if available)
    if track.artist_id:
        kb.row(InlineKeyboardButton(text=t.BTN_ARTIST, callback_data=f"dl:ar:{track.artist_id}"))

    return kb.as_markup()


def audio_effects_kb(track_id: str, t: Texts) -> InlineKeyboardMarkup:
    """Audio effects submenu — replaces post_download_kb on the audio message."""
    kb = InlineKeyboardBuilder()
    effects = [
        ("🎧 8D Audio",    "8d"),
        ("🔊 Bass Boost",  "bass"),
        ("🌌 Reverb",      "reverb"),
        ("🎵 Acoustic",    "acoustic"),
        ("🎤 Vocal Boost", "vocal"),
        ("🎶 Slowed",      "slowed"),
        ("⚡ Nightcore",   "nightcore"),
        ("🌙 Lo-Fi",       "lofi"),
    ]
    for i in range(0, len(effects), 2):
        kb.row(*[
            InlineKeyboardButton(text=label, callback_data=f"ea:apply:{key}:{track_id}")
            for label, key in effects[i:i + 2]
        ])
    kb.row(InlineKeyboardButton(text=t.BTN_BACK, callback_data=f"ea:back:{track_id}"))
    return kb.as_markup()


def metadata_editor_kb(track_id: str, t: Texts) -> InlineKeyboardMarkup:
    """Metadata editor — replaces post_download_kb on the audio message."""
    kb = InlineKeyboardBuilder()
    fields = [
        (t.BTN_META_TITLE,  "title"),
        (t.BTN_META_ARTIST, "artist"),
        (t.BTN_META_ALBUM,  "album"),
        (t.BTN_META_YEAR,   "year"),
        (t.BTN_META_GENRE,  "genre"),
        (t.BTN_META_COVER,  "cover"),
    ]
    for i in range(0, len(fields), 2):
        kb.row(*[
            InlineKeyboardButton(text=label, callback_data=f"em:f:{key}:{track_id}")
            for label, key in fields[i:i + 2]
        ])
    kb.row(InlineKeyboardButton(text=t.BTN_BACK, callback_data=f"em:back:{track_id}"))
    return kb.as_markup()


def recognize_result_kb(track, t: Texts) -> InlineKeyboardMarkup:
    """Keyboard shown after successful music recognition."""
    kb = InlineKeyboardBuilder()
    # Row 1: Download + Save to Favorites
    kb.row(
        InlineKeyboardButton(text=t.BTN_RECOGNIZE_DL, callback_data=f"dl:t:{track.id}"),
        InlineKeyboardButton(text=t.BTN_FAV_ADD, callback_data=f"fav:{track.id}"),
    )
    # Row 2: Similar Songs + Share (native chat picker)
    share_query = store.stash_share(track)
    kb.row(
        InlineKeyboardButton(text=t.BTN_SIMILAR, callback_data=f"sim:{track.id}"),
        InlineKeyboardButton(
            text=t.BTN_SHARE,
            switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
                query=share_query,
                allow_user_chats=True,
                allow_group_chats=True,
                allow_channel_chats=True,
                allow_bot_chats=False,
            ),
        ),
    )
    return kb.as_markup()


def video_result_kb(token: str, t: Texts) -> InlineKeyboardMarkup:
    """Single-button keyboard shown under a downloaded social media video."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t.BTN_FIND_MUSIC, callback_data=f"vm:{token}")
    ]])


def cancel_meta_kb(track_id: str, t: Texts) -> InlineKeyboardMarkup:
    """Single-button keyboard for field-input prompts."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t.BTN_META_CANCEL, callback_data=f"em:cancel:{track_id}")
    ]])


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
