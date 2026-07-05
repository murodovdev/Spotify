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
    BTN_OPEN: str
    BTN_FAV_ADD: str
    BTN_FAV_SAVED: str
    BTN_FAVORITES: str

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
        "🎵 <b>TrackFlow</b> — Spotify yuklovchi\n\n"
        "Salom, {name}! 👋\n"
        "Men Spotify'dagi istalgan <b>qo'shiq</b>, <b>albom</b> yoki <b>playlist</b>ni "
        "yuqori sifatli MP3 qilib yuboraman.\n\n"
        "<b>Boshlash juda oson:</b>\n"
        "🔗 Spotify havolasini tashlang\n"
        "🔍 yoki shunchaki qo'shiq nomini yozing\n\n"
        "<i>Sinab ko'ring</i> 👉 <code>The Weeknd Blinding Lights</code>"
    ),
    HELP=(
        "📖 <b>Qo'llanma</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 <b>Havola orqali</b>\n"
        "Spotify'dan trek, albom, playlist yoki ijrochi havolasini yuboring.\n\n"
        "🔍 <b>Qidiruv orqali</b>\n"
        "Qo'shiq nomini yozing va natijalardan tanlang.\n\n"
        "❤️ <b>Liked Songs</b>\n"
        "/liked — sevimlilaringizni yuklab oling <i>(Spotify Premium kerak)</i>.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ /favorites — saqlangan qo'shiqlaringiz\n"
        "⚙️ /settings — audio sifati va til"
    ),
    CHOOSE_LANG="🌐 <b>Tilni tanlang:</b>",

    BTN_CONNECT="🔗 Spotify ulash",
    BTN_DISCONNECT="🔌 Uzish",
    BTN_LIKED="❤️ Liked Songs",
    BTN_SETTINGS="⚙️ Sozlamalar",
    BTN_ALBUM="💿 Albom",
    BTN_ARTIST="🎤 Ijrochi",
    BTN_CANCEL="✕ Bekor",
    BTN_START_DL="⬇️ Yuklab olish",
    BTN_PREV="← Oldingi",
    BTN_NEXT="Keyingi →",
    BTN_LANG="🌐 Til",
    BTN_OPEN="🔗 Spotify'da ochish",
    BTN_FAV_ADD="🤍 Saqlash",
    BTN_FAV_SAVED="❤️ Saqlangan",
    BTN_FAVORITES="⭐ Sevimlilar",

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
        "<i>Sahifa {page} / {pages}</i>"
    ),
    SEARCH_EMPTY="😔 <b>«{query}»</b> bo'yicha hech narsa topilmadi.\n<i>Boshqa nom bilan urinib ko'ring.</i>",

    CONNECT_PROMPT=(
        "🔗 <b>Spotify'ni ulang</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Liked Songs yuklab olish uchun Spotify hisobingizni ulashingiz kerak."
    ),
    BTN_CONNECT_URL="🟢 Spotify'ga kirish",
    CONNECTED_MSG=(
        "✅ <b>Spotify ulandi!</b>\n"
        "/liked — sevimli qo'shiqlaringizni yuklab oling."
    ),
    ALREADY_CONNECTED=(
        "ℹ️ Spotify allaqachon ulangan.\n"
        "/liked — yuklab olish."
    ),
    DISCONNECTED="🔌 Spotify uzildi.",
    NOT_CONNECTED=(
        "⚠️ Spotify ulanmagan.\n"
        "Avval /start orqali hisobingizni ulang."
    ),

    LIKED_FETCHING="❤️ <i>Liked Songs olinmoqda…</i>",
    LIKED_CONFIRM=(
        "❤️ <b>Liked Songs</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Qo'shiqlar soni: <b>{count}</b>\n\n"
        "<i>Yuklab olishni boshlashni xohlaysizmi?</i>"
    ),
    LIKED_EMPTY="😔 Liked Songs bo'sh.",

    SETTINGS=(
        "⚙️ <b>Sozlamalar</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 Audio sifati: <b>{quality} kbps</b>"
    ),
    QUALITY_SET="✅ {quality} kbps o'rnatildi",
    LANG_SET="✅ O'zbek tili tanlandi",

    ERR_NOT_FOUND="😔 <b>«{name}»</b> uchun audio topilmadi.",
    ERR_TOO_LARGE="⚠️ <b>«{name}»</b> juda katta — Telegram limiti 50 MB.",
    ERR_GENERIC="❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
    ERR_SPOTIFY_LINK=(
        "❓ Havola tanilmadi.\n"
        "<i>Trek, albom, playlist yoki ijrochi havolasini yuboring.</i>"
    ),
    ERR_BUSY=(
        "⏳ Yuklash davom etmoqda.\n"
        "Avval u tugashini kuting yoki bekor qiling."
    ),
    ERR_NO_CREDENTIALS="🔧 Spotify API kalitlari sozlanmagan. Admin'ga murojaat qiling.",
    ERR_PREMIUM=(
        "⭐ <b>Spotify Premium kerak</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Liked Songs uchun ilova egasida Premium bo'lishi shart.\n"
        "<i>Qolgan barcha funksiyalar Premium'siz ishlaydi.</i>"
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
        "🎵 <b>TrackFlow</b> — Spotify downloader\n\n"
        "Hi {name}! 👋\n"
        "I turn any Spotify <b>song</b>, <b>album</b> or <b>playlist</b> into a "
        "high-quality MP3.\n\n"
        "<b>Getting started is easy:</b>\n"
        "🔗 Drop a Spotify link\n"
        "🔍 or just type a song name\n\n"
        "<i>Try it</i> 👉 <code>The Weeknd Blinding Lights</code>"
    ),
    HELP=(
        "📖 <b>How it works</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 <b>Via link</b>\n"
        "Send a Spotify track, album, playlist, or artist link.\n\n"
        "🔍 <b>Via search</b>\n"
        "Type a song name and pick from the results.\n\n"
        "❤️ <b>Liked Songs</b>\n"
        "/liked — download your favorites <i>(requires Spotify Premium)</i>.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ /favorites — your saved songs\n"
        "⚙️ /settings — audio quality & language"
    ),
    CHOOSE_LANG="🌐 <b>Choose language:</b>",

    BTN_CONNECT="🔗 Connect Spotify",
    BTN_DISCONNECT="🔌 Disconnect",
    BTN_LIKED="❤️ Liked Songs",
    BTN_SETTINGS="⚙️ Settings",
    BTN_ALBUM="💿 Album",
    BTN_ARTIST="🎤 Artist",
    BTN_CANCEL="✕ Cancel",
    BTN_START_DL="⬇️ Download",
    BTN_PREV="← Prev",
    BTN_NEXT="Next →",
    BTN_LANG="🌐 Language",
    BTN_OPEN="🔗 Open in Spotify",
    BTN_FAV_ADD="🤍 Save",
    BTN_FAV_SAVED="❤️ Saved",
    BTN_FAVORITES="⭐ Favorites",

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
        "<i>Page {page} of {pages}</i>"
    ),
    SEARCH_EMPTY="😔 Nothing found for <b>«{query}»</b>.\n<i>Try a different name.</i>",

    CONNECT_PROMPT=(
        "🔗 <b>Connect Spotify</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Connect your Spotify account to download Liked Songs."
    ),
    BTN_CONNECT_URL="🟢 Sign in to Spotify",
    CONNECTED_MSG=(
        "✅ <b>Spotify connected!</b>\n"
        "/liked — download your favorite songs."
    ),
    ALREADY_CONNECTED=(
        "ℹ️ Spotify is already connected.\n"
        "/liked — download."
    ),
    DISCONNECTED="🔌 Spotify disconnected.",
    NOT_CONNECTED=(
        "⚠️ Spotify not connected.\n"
        "Use /start to connect your account first."
    ),

    LIKED_FETCHING="❤️ <i>Fetching Liked Songs…</i>",
    LIKED_CONFIRM=(
        "❤️ <b>Liked Songs</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Tracks: <b>{count}</b>\n\n"
        "<i>Ready to start downloading?</i>"
    ),
    LIKED_EMPTY="😔 Liked Songs is empty.",

    SETTINGS=(
        "⚙️ <b>Settings</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 Audio quality: <b>{quality} kbps</b>"
    ),
    QUALITY_SET="✅ {quality} kbps selected",
    LANG_SET="✅ English selected",

    ERR_NOT_FOUND="😔 Audio not found for <b>«{name}»</b>.",
    ERR_TOO_LARGE="⚠️ <b>«{name}»</b> is too large — Telegram limit is 50 MB.",
    ERR_GENERIC="❌ Something went wrong. Try again.",
    ERR_SPOTIFY_LINK=(
        "❓ Unrecognized link.\n"
        "<i>Send a track, album, playlist, or artist link.</i>"
    ),
    ERR_BUSY=(
        "⏳ Download in progress.\n"
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
        "🎵 <b>TrackFlow</b> — загрузчик Spotify\n\n"
        "Привет, {name}! 👋\n"
        "Превращаю любой <b>трек</b>, <b>альбом</b> или <b>плейлист</b> из Spotify "
        "в MP3 высокого качества.\n\n"
        "<b>Начать очень просто:</b>\n"
        "🔗 Пришлите ссылку Spotify\n"
        "🔍 или просто напишите название песни\n\n"
        "<i>Попробуйте</i> 👉 <code>The Weeknd Blinding Lights</code>"
    ),
    HELP=(
        "📖 <b>Как работает?</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 <b>По ссылке</b>\n"
        "Отправьте ссылку на трек, альбом, плейлист или исполнителя из Spotify.\n\n"
        "🔍 <b>По поиску</b>\n"
        "Напишите название песни и выберите из результатов.\n\n"
        "❤️ <b>Liked Songs</b>\n"
        "/liked — загрузить избранное <i>(нужен Spotify Premium)</i>.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ /favorites — ваши сохранённые песни\n"
        "⚙️ /settings — качество звука и язык"
    ),
    CHOOSE_LANG="🌐 <b>Выберите язык:</b>",

    BTN_CONNECT="🔗 Подключить Spotify",
    BTN_DISCONNECT="🔌 Отключить",
    BTN_LIKED="❤️ Liked Songs",
    BTN_SETTINGS="⚙️ Настройки",
    BTN_ALBUM="💿 Альбом",
    BTN_ARTIST="🎤 Исполнитель",
    BTN_CANCEL="✕ Отмена",
    BTN_START_DL="⬇️ Скачать",
    BTN_PREV="← Назад",
    BTN_NEXT="Вперёд →",
    BTN_LANG="🌐 Язык",
    BTN_OPEN="🔗 Открыть в Spotify",
    BTN_FAV_ADD="🤍 Сохранить",
    BTN_FAV_SAVED="❤️ Сохранено",
    BTN_FAVORITES="⭐ Избранное",

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
        "<i>Страница {page} из {pages}</i>"
    ),
    SEARCH_EMPTY="😔 По запросу <b>«{query}»</b> ничего не найдено.\n<i>Попробуйте другое название.</i>",

    CONNECT_PROMPT=(
        "🔗 <b>Подключить Spotify</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Подключите аккаунт Spotify для загрузки Liked Songs."
    ),
    BTN_CONNECT_URL="🟢 Войти в Spotify",
    CONNECTED_MSG=(
        "✅ <b>Spotify подключён!</b>\n"
        "/liked — загрузить любимые песни."
    ),
    ALREADY_CONNECTED=(
        "ℹ️ Spotify уже подключён.\n"
        "/liked — загрузить."
    ),
    DISCONNECTED="🔌 Spotify отключён.",
    NOT_CONNECTED=(
        "⚠️ Spotify не подключён.\n"
        "Используйте /start для подключения аккаунта."
    ),

    LIKED_FETCHING="❤️ <i>Загрузка Liked Songs…</i>",
    LIKED_CONFIRM=(
        "❤️ <b>Liked Songs</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎵 Треков: <b>{count}</b>\n\n"
        "<i>Начать загрузку?</i>"
    ),
    LIKED_EMPTY="😔 Liked Songs пуст.",

    SETTINGS=(
        "⚙️ <b>Настройки</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎧 Качество звука: <b>{quality} kbps</b>"
    ),
    QUALITY_SET="✅ {quality} kbps выбрано",
    LANG_SET="✅ Русский выбран",

    ERR_NOT_FOUND="😔 Аудио для <b>«{name}»</b> не найдено.",
    ERR_TOO_LARGE="⚠️ <b>«{name}»</b> слишком большой — лимит Telegram 50 МБ.",
    ERR_GENERIC="❌ Произошла ошибка. Попробуйте ещё раз.",
    ERR_SPOTIFY_LINK=(
        "❓ Ссылка не распознана.\n"
        "<i>Отправьте ссылку на трек, альбом, плейлист или исполнителя.</i>"
    ),
    ERR_BUSY=(
        "⏳ Идёт загрузка.\n"
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
