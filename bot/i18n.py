"""Lokalizatsiya tizimi — UZ, EN, RU."""

import html
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Texts:
    # --- Welcome / Help ---
    WELCOME: str
    HELP: str
    CHOOSE_LANG: str

    # --- Tugmalar ---
    BTN_CONNECT: str
    BTN_DISCONNECT: str
    BTN_LIKED: str
    BTN_SETTINGS: str
    BTN_ALBUM: str
    BTN_ARTIST: str
    BTN_CANCEL: str
    BTN_START_DL: str
    BTN_PREV: str
    BTN_NEXT: str
    BTN_LANG: str
    BTN_FAV_ADD: str
    BTN_FAV_SAVED: str
    BTN_FAVORITES: str
    BTN_BACK: str
    BTN_HELP: str

    # --- Post-yuklab olish tugmalari ---
    BTN_SHARE: str
    BTN_SIMILAR: str
    BTN_EFFECTS: str
    BTN_EDIT_META: str

    # --- Ulashish izohi (inline share caption) ---
    SHARE_CAPTION: str

    # --- Metadata tahrirlash tugmalari ---
    BTN_META_TITLE: str
    BTN_META_ARTIST: str
    BTN_META_ALBUM: str
    BTN_META_YEAR: str
    BTN_META_GENRE: str
    BTN_META_COVER: str
    BTN_META_CANCEL: str

    # --- Audio effektlar ---
    EFFECTS_PROCESSING: str
    EFFECTS_DONE: str
    EFFECTS_ERROR: str

    # --- O'xshash qo'shiqlar ---
    SIMILAR_SEARCHING: str
    SIMILAR_TITLE: str
    SIMILAR_EMPTY: str

    # --- Metadata muharriri ---
    META_ASK_TITLE: str
    META_ASK_ARTIST: str
    META_ASK_ALBUM: str
    META_ASK_YEAR: str
    META_ASK_GENRE: str
    META_ASK_COVER: str
    META_PROCESSING: str
    META_DONE: str
    META_ERROR: str

    # --- Playlist brauzeri ---
    BTN_PL_SHUFFLE: str
    BTN_PL_SEARCH: str
    BTN_PL_POPULAR: str
    BTN_PL_CLOSE: str
    PL_TRACKS: str
    PL_HINT: str
    PL_SEARCH_PROMPT: str
    PL_SEARCH_EMPTY: str
    PL_SEARCH_TITLE: str

    # --- Sevimlilar ---
    FAV_TITLE: str
    FAV_EMPTY: str
    FAV_ADDED: str
    FAV_REMOVED: str

    # --- Jarayon ---
    SEARCHING: str
    DOWNLOADING: str
    FETCHING_INFO: str

    PROGRESS: str
    COLLECTION_DONE: str
    COLLECTION_FAILED_LIST: str
    COLLECTION_CANCELLED: str
    CONFIRM_COLLECTION: str

    # --- Qidiruv ---
    SEARCH_RESULTS: str
    SEARCH_EMPTY: str

    # --- Spotify ulash ---
    CONNECT_PROMPT: str
    BTN_CONNECT_URL: str
    CONNECTED_MSG: str
    ALREADY_CONNECTED: str
    DISCONNECTED: str
    NOT_CONNECTED: str

    LIKED_FETCHING: str
    LIKED_CONFIRM: str
    LIKED_EMPTY: str

    # --- Sozlamalar ---
    SETTINGS: str
    QUALITY_SET: str
    LANG_SET: str

    # --- Xatolar ---
    ERR_NOT_FOUND: str
    ERR_TOO_LARGE: str
    ERR_GENERIC: str
    ERR_SPOTIFY_LINK: str
    ERR_BUSY: str
    ERR_NO_CREDENTIALS: str
    ERR_PREMIUM: str
    ERR_EXPIRED: str

    # --- Musiqa tanishtirish (recognition) ---
    RECOGNIZING: str
    RECOGNIZE_HEADER: str
    RECOGNIZE_NOT_FOUND: str
    RECOGNIZE_TOO_LARGE: str
    BTN_RECOGNIZE_DL: str

    # --- YouTube audio ---
    YT_PROCESSING: str
    YT_UNAVAILABLE: str
    YT_PLAYLIST_LOADING: str
    YT_PLAYLIST_EMPTY: str
    YT_PLAYLIST_HINT: str

    # --- YouTube: format tanlash ---
    YT_FETCHING: str
    YT_CHOOSE_FORMAT: str
    YT_PREPARING: str
    YT_TOO_LARGE_ALT: str
    BTN_YT_MP3: str
    BTN_YT_M4A: str
    BTN_YT_FLAC: str
    BTN_YT_OPUS: str
    YT_ERR_PRIVATE: str
    YT_ERR_DELETED: str
    YT_ERR_GEO: str
    YT_ERR_LIVE: str
    YT_ERR_AGE: str
    YT_ERR_NETWORK: str
    YT_ERR_BLOCKED: str

    # --- Video download ---
    VIDEO_DOWNLOADING: str
    VIDEO_TOO_LARGE: str
    VIDEO_PRIVATE: str
    VIDEO_ERROR: str
    BTN_FIND_MUSIC: str
    FINDING_MUSIC: str

    # --- Admin ---
    STATS: str

    # --- OAuth sahifa ---
    OAUTH_OK_TITLE: str
    OAUTH_OK_TEXT: str
    OAUTH_CANCEL_TITLE: str
    OAUTH_CANCEL_TEXT: str
    OAUTH_ERROR_TITLE: str
    OAUTH_ERROR_TEXT: str


UZ = Texts(
    WELCOME=(
        "🎵 <b>TrackFlow</b>\n\n"
        "Salom, {name}! 👋\n\n"
        "Spotify havolasi, qo'shiq nomi yoki video, audio va ovozli xabar "
        "yuboring — TrackFlow musiqani topib, bir necha soniya ichida yuboradi.\n\n"
        "<b>✨ Imkoniyatlar:</b>\n"
        "• 🎵 Qo'shiq, albom va playlist\n"
        "• 🔍 Video, audio va ovozli xabardan musiqani aniqlash\n"
        "• 🎧 Yuqori sifatli audio\n"
        "• 🎚 Audio effektlar va metadata tahrirlash\n\n"
        "🚀 Boshlash uchun Spotify havolasini yoki musiqa nomini yuboring."
    ),
    HELP=(
        "📖 <b>Qo'llanma</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 <b>Spotify havolasi</b>\n"
        "Trek, albom, playlist yoki ijrochi havolasini yuboring.\n\n"
        "🔍 <b>Qidiruv orqali</b>\n"
        "Qo'shiq nomini yozing — natijalardan tanlang.\n\n"
        "▶️ <b>YouTube havolasi</b>\n"
        "Video havolasini yuboring — format tanlang (MP3, M4A, FLAC, OPUS). Playlist ham qo'llab-quvvatlanadi.\n\n"
        "📹 <b>Ijtimoiy tarmoq videosi</b>\n"
        "Instagram, TikTok, Facebook, X, Pinterest yoki Vimeo havolasi — video yuklanadi, "
        "so'ng 🎵 tugmasi bilan undagi musiqani aniqlash mumkin.\n\n"
        "🎵 <b>Musiqani aniqlash</b>\n"
        "Audio, ovozli xabar, video yoki dumaloq video yuboring — bot qo'shiqni avtomatik aniqlaydi.\n\n"
        "❤️ <b>Liked Songs</b>\n"
        "Spotify hisobingizni ulab, sevimlilaringizni yuklab oling.\n\n"
        "🎛 <b>Yuklangandan keyin</b>\n"
        "Har bir qo'shiq ostida: 🤍 sevimlilarga saqlash, 🎧 o'xshash qo'shiqlar, "
        "🎚 effektlar, 🖊 teglarni tahrirlash va 📤 ulashish.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ /favorites — saqlangan qo'shiqlar\n"
        "❤️ /liked — Spotify'dagi sevimlilaringiz\n"
        "⚙️ /settings — sifat va til sozlamalari"
    ),
    CHOOSE_LANG="🌐 <b>Tilni tanlang:</b>",

    BTN_SHARE="📤 Ulashish",
    BTN_SIMILAR="🎧 O'xshash",
    BTN_EFFECTS="🎚 Effektlar",
    BTN_EDIT_META="🖊 Ma'lumot",

    SHARE_CAPTION="🎵 @track_drop_bot orqali ulashildi.",

    BTN_META_TITLE="🎵 Sarlavha",
    BTN_META_ARTIST="👤 Ijrochi",
    BTN_META_ALBUM="💿 Albom",
    BTN_META_YEAR="📅 Yil",
    BTN_META_GENRE="🎼 Janr",
    BTN_META_COVER="🖼 Muqova",
    BTN_META_CANCEL="✕ Bekor qilish",

    EFFECTS_PROCESSING="⚙️ <i>{effect} qayta ishlanmoqda…</i>",
    EFFECTS_DONE="✅ {effect} effekti qo'llanildi!",
    EFFECTS_ERROR="❌ Effektni qo'llab bo'lmadi.",

    SIMILAR_SEARCHING="🎧 O'xshash qo'shiqlar qidirilmoqda…",
    SIMILAR_TITLE=(
        "🎧 <b>«{title}»</b> ga o'xshash qo'shiqlar\n"
        "<i>Sahifa {page} / {pages}</i>"
    ),
    SIMILAR_EMPTY="😔 O'xshash qo'shiqlar topilmadi.",

    META_ASK_TITLE="🎵 Yangi <b>sarlavha</b> yozing:",
    META_ASK_ARTIST="👤 Yangi <b>ijrochi</b> nomini yozing:",
    META_ASK_ALBUM="💿 Yangi <b>albom</b> nomini yozing:",
    META_ASK_YEAR="📅 Yangi <b>yil</b> kiriting (masalan: 2024):",
    META_ASK_GENRE="🎼 Yangi <b>janr</b> yozing:",
    META_ASK_COVER="🖼 Yangi muqova sifatida <b>rasm</b> yuboring:",
    META_PROCESSING="⚙️ <i>Fayl yangilanmoqda…</i>",
    META_DONE="✅ Metadata yangilandi!",
    META_ERROR="❌ Metadata yangilab bo'lmadi.",

    RECOGNIZING="🎵 <i>Musiqa tahlil qilinmoqda…</i>",
    RECOGNIZE_HEADER="✅ <b>Qo'shiq aniqlandi!</b>\n━━━━━━━━━━━━━━━━━━━━",
    RECOGNIZE_NOT_FOUND=(
        "😔 <b>Qo'shiq topilmadi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Aniqroq yozilgan yoki shovqinroq bo'lmagan audio yuboring."
    ),
    RECOGNIZE_TOO_LARGE=(
        "⚠️ <b>Fayl juda katta</b>\n"
        "Telegram 20 MB dan katta faylni yuklab ololmaydi."
    ),
    BTN_RECOGNIZE_DL="⬇️ Yuklab olish",

    YT_PROCESSING="▶️ <i>YouTube audio yuklanmoqda…</i>",
    YT_UNAVAILABLE="🔒 Bu video mavjud emas, maxfiy yoki yosh cheklovi bor.",
    YT_PLAYLIST_LOADING="📁 <i>Playlist yuklanmoqda…</i>",
    YT_PLAYLIST_EMPTY="📁 Bu playlist bo'sh yoki mavjud emas.",
    YT_PLAYLIST_HINT="Yuklab olish uchun qo'shiqni tanlang",

    YT_FETCHING="▶️ <i>Video ma'lumotlari olinmoqda…</i>",
    YT_CHOOSE_FORMAT=(
        "🎬 <b>{title}</b>\n"
        "👤 {channel}{duration}\n\n"
        "<i>Yuklab olish formatini tanlang:</i>"
    ),
    YT_PREPARING="⏬ <i>{fmt} tayyorlanmoqda…</i>",
    YT_TOO_LARGE_ALT=(
        "⚠️ <b>{fmt}</b> hajmi {limit} chegarasidan oshdi.\n\n"
        "<i>Kichikroq format tanlang:</i>"
    ),
    BTN_YT_MP3="🎵 MP3 (Eng yaxshi)",
    BTN_YT_M4A="🎧 M4A (Original)",
    BTN_YT_FLAC="🎼 FLAC (Yo'qotishsiz)",
    BTN_YT_OPUS="🎙 OPUS (Yuqori sifat)",
    YT_ERR_PRIVATE="🔒 Bu video maxfiy.",
    YT_ERR_DELETED="🗑 Bu video o'chirilgan yoki mavjud emas.",
    YT_ERR_GEO="🌍 Bu video sizning mintaqangizda mavjud emas.",
    YT_ERR_LIVE="📡 Jonli efirlarni yuklab bo'lmaydi.",
    YT_ERR_AGE="🔞 Bu videoda yosh cheklovi bor.",
    YT_ERR_NETWORK="📡 Tarmoq xatosi. Qaytadan urinib ko'ring.",
    YT_ERR_BLOCKED="⚠️ YouTube hozircha bu videoni bermayapti. Birozdan so'ng urinib ko'ring.",

    VIDEO_DOWNLOADING="📥 <i>{platform} yuklanmoqda…</i>",
    VIDEO_TOO_LARGE=(
        "⚠️ <b>Video juda katta</b>\n"
        "Telegram 50 MB dan katta videoni qabul qilmaydi."
    ),
    VIDEO_PRIVATE="🔒 Bu video mavjud emas yoki maxfiy.",
    VIDEO_ERROR="❌ Videoni yuklab bo'lmadi. Havolani tekshiring.",
    BTN_FIND_MUSIC="🎵 Musiqani topish",
    FINDING_MUSIC="🎵 <i>Musiqa aniqlanmoqda…</i>",

    BTN_CONNECT="🔗 Spotify ulash",
    BTN_DISCONNECT="🔌 Hisobni uzish",
    BTN_LIKED="❤️ Liked Songs",
    BTN_SETTINGS="⚙️ Sozlamalar",
    BTN_ALBUM="💿 Albom",
    BTN_ARTIST="🎤 Ijrochi",
    BTN_CANCEL="✕ Bekor qilish",
    BTN_START_DL="⬇️ Yuklab olish",
    BTN_PREV="⬅️ Oldingi",
    BTN_NEXT="Keyingi ➡️",
    BTN_LANG="🌐 Tilni o'zgartirish",
    BTN_FAV_ADD="🤍 Saqlash",
    BTN_FAV_SAVED="❤️ Saqlangan",
    BTN_FAVORITES="⭐ Sevimlilar",
    BTN_BACK="← Orqaga",
    BTN_HELP="📖 Qo'llanma",

    BTN_PL_SHUFFLE="🎲 Tasodifiy",
    BTN_PL_SEARCH="🔎 Qidirish",
    BTN_PL_POPULAR="⭐ Ommabop",
    BTN_PL_CLOSE="✖️ Yopish",
    PL_TRACKS="trek",
    PL_HINT="Yuklab olish uchun qo'shiqni tanlang 👇",
    PL_SEARCH_PROMPT=(
        "🔎 <b>Playlist ichida qidirish</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Qo'shiq yoki ijrochi nomini yozing:"
    ),
    PL_SEARCH_EMPTY="😔 Bu playlistda hech narsa topilmadi.",
    PL_SEARCH_TITLE="🔎 «{query}» bo'yicha natijalar",

    FAV_TITLE=(
        "⭐ <b>Sevimlilar</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Qayta yuklab olish uchun qo'shiqni tanlang:"
    ),
    FAV_EMPTY=(
        "⭐ <b>Sevimlilar bo'sh</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Qo'shiq ostidagi 🤍 tugmasi orqali sevimlilarga qo'shing."
    ),
    FAV_ADDED="❤️ Sevimlilarga qo'shildi",
    FAV_REMOVED="🤍 Sevimlilardan olib tashlandi",

    SEARCHING="🔍 <i>Qidirilmoqda…</i>",
    DOWNLOADING="⬇️ <i>Yuklanmoqda…</i>",
    FETCHING_INFO="🔄 <i>Ma'lumot olinmoqda…</i>",

    PROGRESS=(
        "⬇️ <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "{bar}  <code>{done}/{total}</code>\n"
        "✅ Yuborildi: <b>{sent}</b>   ❌ Xato: <b>{failed}</b>"
    ),
    COLLECTION_DONE=(
        "✅ <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Yuborildi: <b>{sent}</b> / {total}"
    ),
    COLLECTION_FAILED_LIST="\n⚠️ Topilmadi: <i>{names}</i>",
    COLLECTION_CANCELLED=(
        "⛔ Bekor qilindi\n"
        "Yuborildi: <b>{sent}</b> / {total}"
    ),
    CONFIRM_COLLECTION=(
        "📋 <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Treklar soni: <b>{count}</b>\n\n"
        "<i>Yuklab olishni boshlashni xohlaysizmi?</i>"
    ),

    SEARCH_RESULTS=(
        "🔍 <b>«{query}»</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Sahifa {page} / {pages}</i>"
    ),
    SEARCH_EMPTY=(
        "😔 <b>Hech narsa topilmadi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>«{query}»</i> bo'yicha natija yo'q.\n"
        "Boshqa nom bilan urinib ko'ring."
    ),

    CONNECT_PROMPT=(
        "🔗 <b>Spotify hisobini ulang</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Liked Songs yuklab olish uchun Spotify hisobingizni ulang."
    ),
    BTN_CONNECT_URL="🟢 Spotify'ga kirish",
    CONNECTED_MSG=(
        "✅ <b>Spotify ulandi!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Endi /liked orqali sevimli qo'shiqlaringizni yuklab olishingiz mumkin."
    ),
    ALREADY_CONNECTED=(
        "ℹ️ <b>Spotify allaqachon ulangan</b>\n"
        "❤️ /liked — yuklab olish."
    ),
    DISCONNECTED=(
        "🔌 <b>Spotify uzildi</b>\n"
        "Qayta ulash uchun /start bosing."
    ),
    NOT_CONNECTED=(
        "⚠️ <b>Spotify ulanmagan</b>\n"
        "Avval /start orqali hisobingizni ulang."
    ),

    LIKED_FETCHING="❤️ <i>Liked Songs olinmoqda…</i>",
    LIKED_CONFIRM=(
        "❤️ <b>Liked Songs</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Qo'shiqlar soni: <b>{count}</b>\n\n"
        "<i>Yuklab olishni boshlashni xohlaysizmi?</i>"
    ),
    LIKED_EMPTY=(
        "😔 <b>Liked Songs bo'sh</b>\n"
        "Spotify'da biror qo'shiqni yoqtiring va qayta urinib ko'ring."
    ),

    SETTINGS=(
        "⚙️ <b>Sozlamalar</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 Audio sifati: <b>{quality} kbps</b>"
    ),
    QUALITY_SET="✅ {quality} kbps o'rnatildi",
    LANG_SET="✅ O'zbek tili tanlandi",

    ERR_NOT_FOUND=(
        "😔 <b>Audio topilmadi</b>\n"
        "<i>«{name}»</i> uchun ovoz fayli yo'q."
    ),
    ERR_TOO_LARGE=(
        "⚠️ <b>Fayl juda katta</b>\n"
        "<i>«{name}»</i> — Telegram limiti 50 MB."
    ),
    ERR_GENERIC="❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
    ERR_SPOTIFY_LINK=(
        "❓ <b>Havola tanilmadi</b>\n"
        "Trek, albom, playlist yoki ijrochi havolasini yuboring."
    ),
    ERR_BUSY=(
        "⏳ <b>Yuklash davom etmoqda</b>\n"
        "Avval tugashini kuting yoki bekor qiling."
    ),
    ERR_NO_CREDENTIALS="🔧 Spotify API kalitlari sozlanmagan. Admin'ga murojaat qiling.",
    ERR_PREMIUM=(
        "⭐ <b>Spotify Premium kerak</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Liked Songs uchun ilova egasida Premium bo'lishi shart.\n"
        "<i>Boshqa barcha funksiyalar bepul ishlaydi.</i>"
    ),
    ERR_EXPIRED="⏱ Vaqt tugadi. Qaytadan urinib ko'ring.",

    STATS=(
        "📊 <b>Statistika</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👥 Foydalanuvchilar: <b>{users}</b>\n"
        "⬇️ Yuklab olingan: <b>{downloads}</b>\n"
        "⚡ Keshdan: <b>{cache_hits}</b>\n"
        "💾 Kesh hajmi: <b>{cached}</b> trek\n"
        "📈 Kesh samaradorligi: <b>{hit_rate}%</b>"
    ),

    OAUTH_OK_TITLE="Spotify ulandi!",
    OAUTH_OK_TEXT="Endi Telegram'ga qaytishingiz mumkin.",
    OAUTH_CANCEL_TITLE="Ulanish bekor qilindi",
    OAUTH_CANCEL_TEXT="Telegram'ga qaytib, qaytadan urinib ko'ring.",
    OAUTH_ERROR_TITLE="Xatolik yuz berdi",
    OAUTH_ERROR_TEXT="Telegram'ga qaytib, qaytadan urinib ko'ring.",
)

EN = Texts(
    WELCOME=(
        "🎵 <b>TrackFlow</b>\n\n"
        "Hi, {name}! 👋\n\n"
        "Send a Spotify link, a song name, or a video, audio or voice message "
        "— TrackFlow finds the music and delivers it in seconds.\n\n"
        "<b>✨ What you can do:</b>\n"
        "• 🎵 Songs, albums and playlists\n"
        "• 🔍 Identify music from video, audio and voice messages\n"
        "• 🎧 High-quality audio\n"
        "• 🎚 Audio effects and metadata editing\n\n"
        "🚀 To get started, send a Spotify link or a song name."
    ),
    HELP=(
        "📖 <b>How it works</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 <b>Spotify link</b>\n"
        "Send a track, album, playlist, or artist link.\n\n"
        "🔍 <b>Via search</b>\n"
        "Type a song name and pick from the results.\n\n"
        "▶️ <b>YouTube link</b>\n"
        "Send a video link and pick a format (MP3, M4A, FLAC, OPUS). Playlists are supported too.\n\n"
        "📹 <b>Social media video</b>\n"
        "Instagram, TikTok, Facebook, X, Pinterest or Vimeo link — the video is downloaded, "
        "then the 🎵 button identifies the music in it.\n\n"
        "🎵 <b>Music Recognition</b>\n"
        "Send any audio, voice message, video or round video — the bot will identify the song automatically.\n\n"
        "❤️ <b>Liked Songs</b>\n"
        "Connect your Spotify account to download your favorites.\n\n"
        "🎛 <b>After the download</b>\n"
        "Under every song: 🤍 save to favorites, 🎧 similar songs, "
        "🎚 audio effects, 🖊 tag editor and 📤 share.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ /favorites — your saved songs\n"
        "❤️ /liked — your Spotify Liked Songs\n"
        "⚙️ /settings — quality & language"
    ),
    CHOOSE_LANG="🌐 <b>Choose language:</b>",

    BTN_SHARE="📤 Share",
    BTN_SIMILAR="🎧 Similar",
    BTN_EFFECTS="🎚 Effects",
    BTN_EDIT_META="🖊 Edit Info",

    SHARE_CAPTION="🎵 Shared via @track_drop_bot",

    BTN_META_TITLE="🎵 Title",
    BTN_META_ARTIST="👤 Artist",
    BTN_META_ALBUM="💿 Album",
    BTN_META_YEAR="📅 Year",
    BTN_META_GENRE="🎼 Genre",
    BTN_META_COVER="🖼 Cover",
    BTN_META_CANCEL="✕ Cancel",

    EFFECTS_PROCESSING="⚙️ <i>Applying {effect}…</i>",
    EFFECTS_DONE="✅ {effect} applied!",
    EFFECTS_ERROR="❌ Could not apply effect.",

    SIMILAR_SEARCHING="🎧 Finding similar tracks…",
    SIMILAR_TITLE=(
        "🎧 <b>Songs similar to «{title}»</b>\n"
        "<i>Page {page} of {pages}</i>"
    ),
    SIMILAR_EMPTY="😔 No similar tracks found.",

    META_ASK_TITLE="🎵 Enter new <b>title</b>:",
    META_ASK_ARTIST="👤 Enter new <b>artist</b> name:",
    META_ASK_ALBUM="💿 Enter new <b>album</b> name:",
    META_ASK_YEAR="📅 Enter <b>year</b> (e.g. 2024):",
    META_ASK_GENRE="🎼 Enter <b>genre</b>:",
    META_ASK_COVER="🖼 Send a <b>photo</b> to use as cover art:",
    META_PROCESSING="⚙️ <i>Updating file…</i>",
    META_DONE="✅ Metadata updated!",
    META_ERROR="❌ Could not update metadata.",

    RECOGNIZING="🎵 <i>Analysing music…</i>",
    RECOGNIZE_HEADER="✅ <b>Song Identified!</b>\n━━━━━━━━━━━━━━━━━━━━",
    RECOGNIZE_NOT_FOUND=(
        "😔 <b>Song not found</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Try sending a cleaner or less noisy recording."
    ),
    RECOGNIZE_TOO_LARGE=(
        "⚠️ <b>File too large</b>\n"
        "Telegram can't download files over 20 MB."
    ),
    BTN_RECOGNIZE_DL="⬇️ Download",

    YT_PROCESSING="▶️ <i>Extracting YouTube audio…</i>",
    YT_UNAVAILABLE="🔒 This video is unavailable, private, or age-restricted.",
    YT_PLAYLIST_LOADING="📁 <i>Loading playlist…</i>",
    YT_PLAYLIST_EMPTY="📁 This playlist is empty or unavailable.",
    YT_PLAYLIST_HINT="Select a track to download",

    YT_FETCHING="▶️ <i>Fetching video info…</i>",
    YT_CHOOSE_FORMAT=(
        "🎬 <b>{title}</b>\n"
        "👤 {channel}{duration}\n\n"
        "<i>Choose the download format:</i>"
    ),
    YT_PREPARING="⏬ <i>Preparing {fmt}…</i>",
    YT_TOO_LARGE_ALT=(
        "⚠️ <b>{fmt}</b> exceeds the {limit} limit.\n\n"
        "<i>Pick a smaller format:</i>"
    ),
    BTN_YT_MP3="🎵 MP3 (Best)",
    BTN_YT_M4A="🎧 M4A (Original)",
    BTN_YT_FLAC="🎼 FLAC (Lossless)",
    BTN_YT_OPUS="🎙 OPUS (High Quality)",
    YT_ERR_PRIVATE="🔒 This video is private.",
    YT_ERR_DELETED="🗑 This video was deleted or doesn't exist.",
    YT_ERR_GEO="🌍 This video isn't available in your region.",
    YT_ERR_LIVE="📡 Live streams can't be downloaded.",
    YT_ERR_AGE="🔞 This video is age-restricted.",
    YT_ERR_NETWORK="📡 Network error. Please try again.",
    YT_ERR_BLOCKED="⚠️ YouTube is refusing this video right now. Please try again shortly.",

    VIDEO_DOWNLOADING="📥 <i>Downloading {platform}…</i>",
    VIDEO_TOO_LARGE=(
        "⚠️ <b>Video too large</b>\n"
        "Telegram can't send videos over 50 MB."
    ),
    VIDEO_PRIVATE="🔒 This video is unavailable or private.",
    VIDEO_ERROR="❌ Could not download the video. Check the link.",
    BTN_FIND_MUSIC="🎵 Find Music",
    FINDING_MUSIC="🎵 <i>Identifying music…</i>",

    BTN_CONNECT="🔗 Connect Spotify",
    BTN_DISCONNECT="🔌 Disconnect account",
    BTN_LIKED="❤️ Liked Songs",
    BTN_SETTINGS="⚙️ Settings",
    BTN_ALBUM="💿 Album",
    BTN_ARTIST="🎤 Artist",
    BTN_CANCEL="✕ Cancel",
    BTN_START_DL="⬇️ Download",
    BTN_PREV="⬅️ Prev",
    BTN_NEXT="Next ➡️",
    BTN_LANG="🌐 Change language",
    BTN_FAV_ADD="🤍 Save",
    BTN_FAV_SAVED="❤️ Saved",
    BTN_FAVORITES="⭐ Favorites",
    BTN_BACK="← Back",
    BTN_HELP="📖 Help",

    BTN_PL_SHUFFLE="🎲 Shuffle",
    BTN_PL_SEARCH="🔎 Search",
    BTN_PL_POPULAR="⭐ Popular",
    BTN_PL_CLOSE="✖️ Close",
    PL_TRACKS="tracks",
    PL_HINT="Tap a song to download it 👇",
    PL_SEARCH_PROMPT=(
        "🔎 <b>Search in playlist</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Type a song or artist name:"
    ),
    PL_SEARCH_EMPTY="😔 Nothing found in this playlist.",
    PL_SEARCH_TITLE="🔎 Results for «{query}»",

    FAV_TITLE=(
        "⭐ <b>Favorites</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Pick a song to download it again:"
    ),
    FAV_EMPTY=(
        "⭐ <b>No favorites yet</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Tap the 🤍 button under any song to save it here."
    ),
    FAV_ADDED="❤️ Added to favorites",
    FAV_REMOVED="🤍 Removed from favorites",

    SEARCHING="🔍 <i>Searching…</i>",
    DOWNLOADING="⬇️ <i>Downloading…</i>",
    FETCHING_INFO="🔄 <i>Fetching info…</i>",

    PROGRESS=(
        "⬇️ <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "{bar}  <code>{done}/{total}</code>\n"
        "✅ Sent: <b>{sent}</b>   ❌ Failed: <b>{failed}</b>"
    ),
    COLLECTION_DONE=(
        "✅ <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Sent: <b>{sent}</b> / {total}"
    ),
    COLLECTION_FAILED_LIST="\n⚠️ Not found: <i>{names}</i>",
    COLLECTION_CANCELLED=(
        "⛔ Cancelled\n"
        "Sent: <b>{sent}</b> / {total}"
    ),
    CONFIRM_COLLECTION=(
        "📋 <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Tracks: <b>{count}</b>\n\n"
        "<i>Ready to start downloading?</i>"
    ),

    SEARCH_RESULTS=(
        "🔍 <b>«{query}»</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Page {page} of {pages}</i>"
    ),
    SEARCH_EMPTY=(
        "😔 <b>Nothing found</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "No results for <i>«{query}»</i>.\n"
        "Try a different name."
    ),

    CONNECT_PROMPT=(
        "🔗 <b>Connect Spotify</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Connect your Spotify account to download Liked Songs."
    ),
    BTN_CONNECT_URL="🟢 Sign in to Spotify",
    CONNECTED_MSG=(
        "✅ <b>Spotify connected!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Use /liked to download your favorite songs."
    ),
    ALREADY_CONNECTED=(
        "ℹ️ <b>Spotify already connected</b>\n"
        "❤️ /liked — download."
    ),
    DISCONNECTED=(
        "🔌 <b>Spotify disconnected</b>\n"
        "Use /start to reconnect."
    ),
    NOT_CONNECTED=(
        "⚠️ <b>Spotify not connected</b>\n"
        "Use /start to connect your account first."
    ),

    LIKED_FETCHING="❤️ <i>Fetching Liked Songs…</i>",
    LIKED_CONFIRM=(
        "❤️ <b>Liked Songs</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Tracks: <b>{count}</b>\n\n"
        "<i>Ready to start downloading?</i>"
    ),
    LIKED_EMPTY=(
        "😔 <b>Liked Songs is empty</b>\n"
        "Like some songs on Spotify and try again."
    ),

    SETTINGS=(
        "⚙️ <b>Settings</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 Audio quality: <b>{quality} kbps</b>"
    ),
    QUALITY_SET="✅ {quality} kbps selected",
    LANG_SET="✅ English selected",

    ERR_NOT_FOUND=(
        "😔 <b>Audio not found</b>\n"
        "No audio file for <i>«{name}»</i>."
    ),
    ERR_TOO_LARGE=(
        "⚠️ <b>File too large</b>\n"
        "<i>«{name}»</i> — Telegram limit is 50 MB."
    ),
    ERR_GENERIC="❌ Something went wrong. Try again.",
    ERR_SPOTIFY_LINK=(
        "❓ <b>Unrecognized link</b>\n"
        "Send a track, album, playlist, or artist link."
    ),
    ERR_BUSY=(
        "⏳ <b>Download in progress</b>\n"
        "Wait for it to finish or cancel it."
    ),
    ERR_NO_CREDENTIALS="🔧 Spotify API keys are not configured. Contact the admin.",
    ERR_PREMIUM=(
        "⭐ <b>Spotify Premium required</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "The app owner needs Premium for Liked Songs.\n"
        "<i>All other features work without Premium.</i>"
    ),
    ERR_EXPIRED="⏱ Session expired. Try again.",

    STATS=(
        "📊 <b>Stats</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👥 Users: <b>{users}</b>\n"
        "⬇️ Downloads: <b>{downloads}</b>\n"
        "⚡ Cache hits: <b>{cache_hits}</b>\n"
        "💾 Cached tracks: <b>{cached}</b>\n"
        "📈 Cache hit rate: <b>{hit_rate}%</b>"
    ),

    OAUTH_OK_TITLE="Spotify connected!",
    OAUTH_OK_TEXT="You can return to Telegram now.",
    OAUTH_CANCEL_TITLE="Connection cancelled",
    OAUTH_CANCEL_TEXT="Go back to Telegram and try again.",
    OAUTH_ERROR_TITLE="Something went wrong",
    OAUTH_ERROR_TEXT="Go back to Telegram and try again.",
)

RU = Texts(
    WELCOME=(
        "🎵 <b>TrackFlow</b>\n\n"
        "Привет, {name}! 👋\n\n"
        "Отправьте ссылку Spotify, название песни или видео, аудио либо "
        "голосовое сообщение — TrackFlow найдёт музыку и пришлёт её за "
        "несколько секунд.\n\n"
        "<b>✨ Возможности:</b>\n"
        "• 🎵 Песни, альбомы и плейлисты\n"
        "• 🔍 Распознавание музыки из видео, аудио и голосовых\n"
        "• 🎧 Аудио высокого качества\n"
        "• 🎚 Аудиоэффекты и редактирование метаданных\n\n"
        "🚀 Чтобы начать, отправьте ссылку Spotify или название песни."
    ),
    HELP=(
        "📖 <b>Как работает?</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 <b>Ссылка Spotify</b>\n"
        "Отправьте ссылку на трек, альбом, плейлист или исполнителя.\n\n"
        "🔍 <b>По поиску</b>\n"
        "Напишите название песни — выберите из результатов.\n\n"
        "▶️ <b>Ссылка YouTube</b>\n"
        "Отправьте ссылку на видео и выберите формат (MP3, M4A, FLAC, OPUS). Плейлисты тоже поддерживаются.\n\n"
        "📹 <b>Видео из соцсетей</b>\n"
        "Ссылка на Instagram, TikTok, Facebook, X, Pinterest или Vimeo — видео скачается, "
        "а кнопка 🎵 распознает музыку из него.\n\n"
        "🎵 <b>Распознавание музыки</b>\n"
        "Отправьте аудио, голосовое сообщение, видео или кружок — бот автоматически определит песню.\n\n"
        "❤️ <b>Liked Songs</b>\n"
        "Подключите аккаунт Spotify и скачивайте избранное.\n\n"
        "🎛 <b>После загрузки</b>\n"
        "Под каждой песней: 🤍 сохранить в избранное, 🎧 похожие песни, "
        "🎚 эффекты, 🖊 редактор тегов и 📤 поделиться.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ /favorites — сохранённые песни\n"
        "❤️ /liked — избранное из Spotify\n"
        "⚙️ /settings — качество и язык"
    ),
    CHOOSE_LANG="🌐 <b>Выберите язык:</b>",

    BTN_SHARE="📤 Поделиться",
    BTN_SIMILAR="🎧 Похожие",
    BTN_EFFECTS="🎚 Эффекты",
    BTN_EDIT_META="🖊 Инфо",

    SHARE_CAPTION="🎵 Отправлено через @track_drop_bot",

    BTN_META_TITLE="🎵 Название",
    BTN_META_ARTIST="👤 Исполнитель",
    BTN_META_ALBUM="💿 Альбом",
    BTN_META_YEAR="📅 Год",
    BTN_META_GENRE="🎼 Жанр",
    BTN_META_COVER="🖼 Обложка",
    BTN_META_CANCEL="✕ Отмена",

    EFFECTS_PROCESSING="⚙️ <i>Применяю {effect}…</i>",
    EFFECTS_DONE="✅ {effect} применён!",
    EFFECTS_ERROR="❌ Не удалось применить эффект.",

    SIMILAR_SEARCHING="🎧 Ищу похожие треки…",
    SIMILAR_TITLE=(
        "🎧 <b>Похожие на «{title}»</b>\n"
        "<i>Страница {page} из {pages}</i>"
    ),
    SIMILAR_EMPTY="😔 Похожих треков не найдено.",

    META_ASK_TITLE="🎵 Введите новое <b>название</b>:",
    META_ASK_ARTIST="👤 Введите нового <b>исполнителя</b>:",
    META_ASK_ALBUM="💿 Введите новый <b>альбом</b>:",
    META_ASK_YEAR="📅 Введите <b>год</b> (например: 2024):",
    META_ASK_GENRE="🎼 Введите <b>жанр</b>:",
    META_ASK_COVER="🖼 Отправьте <b>фото</b> для обложки:",
    META_PROCESSING="⚙️ <i>Обновляю файл…</i>",
    META_DONE="✅ Метаданные обновлены!",
    META_ERROR="❌ Не удалось обновить метаданные.",

    RECOGNIZING="🎵 <i>Анализирую музыку…</i>",
    RECOGNIZE_HEADER="✅ <b>Песня определена!</b>\n━━━━━━━━━━━━━━━━━━━━",
    RECOGNIZE_NOT_FOUND=(
        "😔 <b>Песня не найдена</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Попробуйте отправить более чистую запись без шумов."
    ),
    RECOGNIZE_TOO_LARGE=(
        "⚠️ <b>Файл слишком большой</b>\n"
        "Telegram не может скачать файлы больше 20 МБ."
    ),
    BTN_RECOGNIZE_DL="⬇️ Скачать",

    YT_PROCESSING="▶️ <i>Извлекаю аудио из YouTube…</i>",
    YT_UNAVAILABLE="🔒 Это видео недоступно, приватное или с возрастным ограничением.",
    YT_PLAYLIST_LOADING="📁 <i>Загружаю плейлист…</i>",
    YT_PLAYLIST_EMPTY="📁 Этот плейлист пуст или недоступен.",
    YT_PLAYLIST_HINT="Выберите трек для загрузки",

    YT_FETCHING="▶️ <i>Получаю информацию о видео…</i>",
    YT_CHOOSE_FORMAT=(
        "🎬 <b>{title}</b>\n"
        "👤 {channel}{duration}\n\n"
        "<i>Выберите формат загрузки:</i>"
    ),
    YT_PREPARING="⏬ <i>Готовлю {fmt}…</i>",
    YT_TOO_LARGE_ALT=(
        "⚠️ <b>{fmt}</b> превышает лимит {limit}.\n\n"
        "<i>Выберите формат поменьше:</i>"
    ),
    BTN_YT_MP3="🎵 MP3 (Лучший)",
    BTN_YT_M4A="🎧 M4A (Оригинал)",
    BTN_YT_FLAC="🎼 FLAC (Без потерь)",
    BTN_YT_OPUS="🎙 OPUS (Высокое качество)",
    YT_ERR_PRIVATE="🔒 Это видео приватное.",
    YT_ERR_DELETED="🗑 Видео удалено или не существует.",
    YT_ERR_GEO="🌍 Видео недоступно в вашем регионе.",
    YT_ERR_LIVE="📡 Прямые трансляции скачать нельзя.",
    YT_ERR_AGE="🔞 На видео возрастное ограничение.",
    YT_ERR_NETWORK="📡 Ошибка сети. Попробуйте снова.",
    YT_ERR_BLOCKED="⚠️ YouTube сейчас не отдаёт это видео. Попробуйте чуть позже.",

    VIDEO_DOWNLOADING="📥 <i>Загружаю {platform}…</i>",
    VIDEO_TOO_LARGE=(
        "⚠️ <b>Видео слишком большое</b>\n"
        "Telegram не принимает видео больше 50 МБ."
    ),
    VIDEO_PRIVATE="🔒 Это видео недоступно или приватное.",
    VIDEO_ERROR="❌ Не удалось загрузить видео. Проверьте ссылку.",
    BTN_FIND_MUSIC="🎵 Найти музыку",
    FINDING_MUSIC="🎵 <i>Определяю музыку…</i>",

    BTN_CONNECT="🔗 Подключить Spotify",
    BTN_DISCONNECT="🔌 Отключить аккаунт",
    BTN_LIKED="❤️ Liked Songs",
    BTN_SETTINGS="⚙️ Настройки",
    BTN_ALBUM="💿 Альбом",
    BTN_ARTIST="🎤 Исполнитель",
    BTN_CANCEL="✕ Отмена",
    BTN_START_DL="⬇️ Скачать",
    BTN_PREV="⬅️ Назад",
    BTN_NEXT="Вперёд ➡️",
    BTN_LANG="🌐 Изменить язык",
    BTN_FAV_ADD="🤍 Сохранить",
    BTN_FAV_SAVED="❤️ Сохранено",
    BTN_FAVORITES="⭐ Избранное",
    BTN_BACK="← Назад",
    BTN_HELP="📖 Справка",

    BTN_PL_SHUFFLE="🎲 Случайно",
    BTN_PL_SEARCH="🔎 Поиск",
    BTN_PL_POPULAR="⭐ Популярное",
    BTN_PL_CLOSE="✖️ Закрыть",
    PL_TRACKS="треков",
    PL_HINT="Нажмите на песню, чтобы скачать 👇",
    PL_SEARCH_PROMPT=(
        "🔎 <b>Поиск в плейлисте</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Введите название песни или исполнителя:"
    ),
    PL_SEARCH_EMPTY="😔 В этом плейлисте ничего не найдено.",
    PL_SEARCH_TITLE="🔎 Результаты по «{query}»",

    FAV_TITLE=(
        "⭐ <b>Избранное</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выберите песню, чтобы скачать снова:"
    ),
    FAV_EMPTY=(
        "⭐ <b>Избранное пусто</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Нажмите 🤍 под любой песней, чтобы сохранить её здесь."
    ),
    FAV_ADDED="❤️ Добавлено в избранное",
    FAV_REMOVED="🤍 Удалено из избранного",

    SEARCHING="🔍 <i>Поиск…</i>",
    DOWNLOADING="⬇️ <i>Загрузка…</i>",
    FETCHING_INFO="🔄 <i>Получение данных…</i>",

    PROGRESS=(
        "⬇️ <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "{bar}  <code>{done}/{total}</code>\n"
        "✅ Отправлено: <b>{sent}</b>   ❌ Ошибок: <b>{failed}</b>"
    ),
    COLLECTION_DONE=(
        "✅ <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Отправлено: <b>{sent}</b> / {total}"
    ),
    COLLECTION_FAILED_LIST="\n⚠️ Не найдено: <i>{names}</i>",
    COLLECTION_CANCELLED=(
        "⛔ Отменено\n"
        "Отправлено: <b>{sent}</b> / {total}"
    ),
    CONFIRM_COLLECTION=(
        "📋 <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Треков: <b>{count}</b>\n\n"
        "<i>Начать загрузку?</i>"
    ),

    SEARCH_RESULTS=(
        "🔍 <b>«{query}»</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Страница {page} из {pages}</i>"
    ),
    SEARCH_EMPTY=(
        "😔 <b>Ничего не найдено</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "По запросу <i>«{query}»</i> результатов нет.\n"
        "Попробуйте другое название."
    ),

    CONNECT_PROMPT=(
        "🔗 <b>Подключить Spotify</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Подключите аккаунт Spotify для загрузки Liked Songs."
    ),
    BTN_CONNECT_URL="🟢 Войти в Spotify",
    CONNECTED_MSG=(
        "✅ <b>Spotify подключён!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Используйте /liked для загрузки любимых песен."
    ),
    ALREADY_CONNECTED=(
        "ℹ️ <b>Spotify уже подключён</b>\n"
        "❤️ /liked — загрузить."
    ),
    DISCONNECTED=(
        "🔌 <b>Spotify отключён</b>\n"
        "Используйте /start для повторного подключения."
    ),
    NOT_CONNECTED=(
        "⚠️ <b>Spotify не подключён</b>\n"
        "Используйте /start для подключения аккаунта."
    ),

    LIKED_FETCHING="❤️ <i>Загрузка Liked Songs…</i>",
    LIKED_CONFIRM=(
        "❤️ <b>Liked Songs</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Треков: <b>{count}</b>\n\n"
        "<i>Начать загрузку?</i>"
    ),
    LIKED_EMPTY=(
        "😔 <b>Liked Songs пуст</b>\n"
        "Поставьте лайки песням в Spotify и попробуйте снова."
    ),

    SETTINGS=(
        "⚙️ <b>Настройки</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 Качество звука: <b>{quality} kbps</b>"
    ),
    QUALITY_SET="✅ {quality} kbps выбрано",
    LANG_SET="✅ Русский выбран",

    ERR_NOT_FOUND=(
        "😔 <b>Аудио не найдено</b>\n"
        "Файл для <i>«{name}»</i> недоступен."
    ),
    ERR_TOO_LARGE=(
        "⚠️ <b>Файл слишком большой</b>\n"
        "<i>«{name}»</i> — лимит Telegram 50 МБ."
    ),
    ERR_GENERIC="❌ Произошла ошибка. Попробуйте ещё раз.",
    ERR_SPOTIFY_LINK=(
        "❓ <b>Ссылка не распознана</b>\n"
        "Отправьте ссылку на трек, альбом, плейлист или исполнителя."
    ),
    ERR_BUSY=(
        "⏳ <b>Идёт загрузка</b>\n"
        "Дождитесь завершения или отмените."
    ),
    ERR_NO_CREDENTIALS="🔧 API-ключи Spotify не настроены. Обратитесь к администратору.",
    ERR_PREMIUM=(
        "⭐ <b>Нужен Spotify Premium</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Для Liked Songs владельцу приложения нужен Premium.\n"
        "<i>Все остальные функции работают без Premium.</i>"
    ),
    ERR_EXPIRED="⏱ Сессия устарела. Попробуйте снова.",

    STATS=(
        "📊 <b>Статистика</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👥 Пользователи: <b>{users}</b>\n"
        "⬇️ Загрузки: <b>{downloads}</b>\n"
        "⚡ Из кеша: <b>{cache_hits}</b>\n"
        "💾 В кеше: <b>{cached}</b> треков\n"
        "📈 Эффективность: <b>{hit_rate}%</b>"
    ),

    OAUTH_OK_TITLE="Spotify подключён!",
    OAUTH_OK_TEXT="Вернитесь в Telegram.",
    OAUTH_CANCEL_TITLE="Подключение отменено",
    OAUTH_CANCEL_TEXT="Вернитесь в Telegram и попробуйте снова.",
    OAUTH_ERROR_TITLE="Произошла ошибка",
    OAUTH_ERROR_TEXT="Вернитесь в Telegram и попробуйте снова.",
)

LANGUAGES = {"uz": UZ, "en": EN, "ru": RU}
LANG_LABELS = {"uz": "🇺🇿 O'zbek", "en": "🇬🇧 English", "ru": "🇷🇺 Русский"}
DEFAULT_LANG = "uz"

# Til tanlanmagan birinchi ekran — hech bir tilga bog'liq emas.
WELCOME_BANNER = (
    "🎵 <b>TrackFlow</b>\n"
    "<i>Spotify → MP3</i>\n\n"
    "🌐 Tilni tanlang · Choose language · Выберите язык"
)


def get_texts(lang: str | None) -> Texts:
    return LANGUAGES.get(lang or DEFAULT_LANG, UZ)


OAUTH_SUCCESS_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: #0d0d0d;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 24px;
  }}
  .card {{
    text-align: center;
    padding: 52px 40px;
    background: linear-gradient(145deg, #1a1a1a, #141414);
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 28px;
    box-shadow: 0 20px 60px rgba(0,0,0,.6);
    max-width: 380px;
    width: 100%;
    animation: pop .35s cubic-bezier(.34,1.56,.64,1) both;
  }}
  @keyframes pop {{
    from {{ transform: scale(.85); opacity: 0; }}
    to   {{ transform: scale(1);   opacity: 1; }}
  }}
  .icon {{ font-size: 72px; line-height: 1; margin-bottom: 20px; }}
  .divider {{
    width: 48px; height: 3px;
    background: #1DB954;
    border-radius: 2px;
    margin: 20px auto;
  }}
  h1 {{ font-size: 22px; font-weight: 700; color: #fff; letter-spacing: -.3px; }}
  p  {{ color: #888; font-size: 15px; line-height: 1.6; margin-top: 10px; }}
  .brand {{
    margin-top: 32px;
    font-size: 12px;
    color: #333;
    letter-spacing: .5px;
    text-transform: uppercase;
  }}
  .brand span {{ color: #1DB954; }}
</style>
</head>
<body>
<div class="card">
  <div class="icon">{icon}</div>
  <h1>{title}</h1>
  <div class="divider"></div>
  <p>{text}</p>
  <div class="brand"><span>Track</span>Flow</div>
</div>
</body>
</html>"""


def progress_bar(done: int, total: int, width: int = 10) -> str:
    filled = int(width * done / total) if total else 0
    pct = int(100 * done / total) if total else 0
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {pct}%"


def playlist_header(playlist, page: int, pages: int, t: Texts) -> str:
    """Playlist brauzeri sarlavhasi (rasm izohi yoki matn xabari)."""
    esc = html.escape
    lines = [f"🎧 <b>{esc(playlist.title)}</b>"]
    if playlist.creator:
        lines.append(f"👤 {esc(playlist.creator)}")
    meta = f"💿 {playlist.total} {t.PL_TRACKS}"
    if pages > 1:
        meta += f"  ·  {page + 1}/{pages}"
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(meta)
    lines.append(f"<i>{t.PL_HINT}</i>")
    return "\n".join(lines)


def track_caption(track) -> str:
    """Trek uchun ma'lumot kartasi (audio ostidagi izoh).

    Faqat mavjud maydonlar ko'rsatiladi — bo'sh janr/yil/albom yozilmaydi.
    Oxirgi <code> qatori Telegram'da bir bosishda nusxalanadi.
    """
    esc = html.escape
    lines = [f"🎵 <b>{esc(track.title)}</b>"]
    if track.artists:
        lines.append(f"👤 {esc(track.artists)}")

    meta: list[str] = []
    if track.album:
        meta.append(f"💿 {esc(track.album)}")
    if getattr(track, "genre", ""):
        meta.append(f"🎼 {esc(track.genre)}")
    if track.year:
        meta.append(f"📅 {track.year}")
    if track.duration:
        mins, secs = divmod(track.duration, 60)
        meta.append(f"⏱ {mins}:{secs:02d}")
    if meta:
        lines.append(" · ".join(meta))

    lines.append(f"<code>{esc(track.artists)} — {esc(track.title)}</code>")
    return "\n".join(lines)
