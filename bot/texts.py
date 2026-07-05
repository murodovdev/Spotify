"""Barcha foydalanuvchi matnlari (o'zbek tilida, HTML formatda)."""

WELCOME = (
    "🎧 <b>Salom, {name}!</b>\n\n"
    "Men Spotify'dagi istalgan musiqani bir zumda topib beraman.\n\n"
    "🔗 Menga <b>Spotify havolasini</b> yuboring — trek, albom, playlist yoki ijrochi\n"
    "🔍 Yoki shunchaki <b>qo'shiq nomini yozing</b> — o'zim topaman\n"
    "❤️ Spotify hisobingizni ulab, <b>Liked Songs</b>'ni to'liq yuklab oling\n\n"
    "Quyidagi menyudan boshlang 👇"
)

HELP = (
    "📖 <b>Qo'llanma</b>\n\n"
    "🔗 <b>Havola yuborish</b>\n"
    "Spotify'dan istalgan havolani tashlang:\n"
    "• Trek — darhol MP3 keladi\n"
    "• Albom / Playlist — barcha treklar navbat bilan\n"
    "• Ijrochi — eng mashhur 10 trek\n\n"
    "🔍 <b>Qidiruv</b>\n"
    "Shunchaki qo'shiq yoki ijrochi nomini yozing:\n"
    "<i>masalan: Xamdam Sobirov To'xta</i>\n\n"
    "❤️ <b>Liked Songs</b>\n"
    "«Spotify ulash» tugmasi orqali hisobingizni ulang,\n"
    "so'ng /liked buyrug'i bilan sevimli qo'shiqlaringizni yuklab oling.\n\n"
    "⚙️ <b>Buyruqlar</b>\n"
    "/start — asosiy menyu\n"
    "/liked — Liked Songs yuklab olish\n"
    "/settings — sifat sozlamalari\n"
    "/history — oxirgi yuklab olinganlar\n"
    "/help — shu qo'llanma"
)

# --- Menyu / tugma yorliqlari ---
BTN_CONNECT = "🔗 Spotify ulash"
BTN_DISCONNECT = "⛓️‍💥 Uzish"
BTN_LIKED = "❤️ Liked Songs"
BTN_SETTINGS = "⚙️ Sozlamalar"
BTN_HISTORY = "📜 Tarix"
BTN_HELP = "ℹ️ Yordam"
BTN_ALBUM = "💿 Albom"
BTN_ARTIST = "👤 Top treklar"
BTN_SPOTIFY = "🎧 Spotify'da ochish"
BTN_CANCEL = "❌ Bekor qilish"
BTN_START_DL = "▶️ Yuklashni boshlash"
BTN_PREV = "⬅️"
BTN_NEXT = "➡️"

# --- Jarayon xabarlari ---
SEARCHING = "🔍 Qidirilmoqda…"
DOWNLOADING = "⬇️ Yuklanmoqda…"
FETCHING_INFO = "⏳ Ma'lumot olinmoqda…"

PROGRESS = (
    "{icon} <b>{title}</b>\n\n"
    "{bar}  <b>{done}/{total}</b>\n"
    "✅ Yuborildi: {sent}   ⚠️ Topilmadi: {failed}"
)

COLLECTION_DONE = (
    "✅ <b>{title}</b> — tayyor!\n\n"
    "🎵 Yuborildi: <b>{sent}/{total}</b>"
)
COLLECTION_FAILED_LIST = "\n⚠️ Topilmadi: {names}"
COLLECTION_CANCELLED = "❌ Bekor qilindi. Yuborilgani: {sent}/{total}"

CONFIRM_COLLECTION = (
    "📀 <b>{title}</b>\n"
    "🎵 Treklar soni: <b>{count}</b>\n\n"
    "Yuklashni boshlaymi?"
)

# --- Qidiruv ---
SEARCH_RESULTS = "🔍 <b>«{query}»</b> bo'yicha natijalar ({page}/{pages}):"
SEARCH_EMPTY = "😔 <b>«{query}»</b> bo'yicha hech narsa topilmadi.\n\nBoshqacha yozib ko'ring."

# --- Spotify ulash ---
CONNECT_PROMPT = (
    "🔗 <b>Spotify hisobingizni ulash</b>\n\n"
    "Quyidagi tugmani bosib, Spotify'ga kiring va ruxsat bering.\n"
    "Shundan so'ng Liked Songs kutubxonangizni yuklab olishingiz mumkin bo'ladi."
)
BTN_CONNECT_URL = "🎧 Spotify'ga kirish"
CONNECTED_MSG = "✅ <b>Spotify muvaffaqiyatli ulandi!</b>\n\nEndi /liked buyrug'i bilan sevimli qo'shiqlaringizni yuklab olishingiz mumkin. ❤️"
ALREADY_CONNECTED = "✅ Spotify allaqachon ulangan.\n\n/liked — Liked Songs'ni yuklab olish"
DISCONNECTED = "⛓️‍💥 Spotify hisobingiz uzildi."
NOT_CONNECTED = (
    "❗ Avval Spotify hisobingizni ulashingiz kerak.\n\n"
    "Buning uchun quyidagi tugmani bosing 👇"
)

LIKED_FETCHING = "⏳ Liked Songs ro'yxati olinmoqda…"
LIKED_CONFIRM = (
    "❤️ <b>Liked Songs</b>\n"
    "🎵 Sizda <b>{count}</b> ta sevimli qo'shiq bor.\n\n"
    "Hammasini yuklashni boshlaymi?"
)
LIKED_EMPTY = "😔 Liked Songs bo'sh ekan."

# --- Sozlamalar ---
SETTINGS = (
    "⚙️ <b>Sozlamalar</b>\n\n"
    "🎚 Audio sifati: <b>{quality} kbps</b>\n\n"
    "Sifatni tanlang:"
)
QUALITY_SET = "✅ Sifat {quality} kbps qilib o'rnatildi."

# --- Tarix ---
HISTORY_TITLE = "📜 <b>Oxirgi yuklab olinganlar</b>\n\nQayta yuborish uchun trekni bosing:"
HISTORY_EMPTY = "📜 Tarix hozircha bo'sh.\n\nBirorta trek yuklab oling — shu yerda ko'rinadi."

# --- Xatolar ---
ERR_NOT_FOUND = "😔 <b>{name}</b> uchun audio topilmadi."
ERR_TOO_LARGE = "⚠️ <b>{name}</b> juda katta (50 MB dan oshadi) — Telegram orqali yuborib bo'lmaydi."
ERR_GENERIC = "⚠️ Xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."
ERR_SPOTIFY_LINK = "🤔 Bu havolani tushunmadim. Trek, albom, playlist yoki ijrochi havolasini yuboring."
ERR_BUSY = "⏳ Sizda hozir aktiv yuklash bor. Avval u tugashini kutingu yoki bekor qiling."
ERR_NO_CREDENTIALS = (
    "⚠️ Bu funksiya uchun Spotify API kalitlari kerak.\n"
    "Admin .env faylga SPOTIFY_CLIENT_ID va SPOTIFY_CLIENT_SECRET qo'shishi kerak."
)
ERR_PREMIUM = (
    "⚠️ Spotify API bu so'rovni rad etdi: 2025-yildan boshlab API ilovasi egasining "
    "hisobida <b>Spotify Premium</b> bo'lishi talab qilinadi.\n\n"
    "Liked Songs funksiyasi uchun API ilovasini yaratgan hisobga Premium ulang. "
    "Qolgan barcha funksiyalar (havola, qidiruv, albom, playlist) Premium'siz ham ishlaydi."
)
ERR_EXPIRED = "⌛ Bu tugma eskirgan. Qaytadan urinib ko'ring."

# --- Admin ---
STATS = (
    "📊 <b>Statistika</b>\n\n"
    "👥 Foydalanuvchilar: <b>{users}</b>\n"
    "🎵 Yuklab olingan treklar: <b>{downloads}</b>\n"
    "⚡ Keshdan yuborilgan: <b>{cache_hits}</b>\n"
    "💾 Keshdagi treklar: <b>{cached}</b>\n"
    "📈 Kesh samaradorligi: <b>{hit_rate}%</b>"
)

OAUTH_SUCCESS_PAGE = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spotify ulandi</title>
<style>
  body {{ margin:0; font-family:system-ui,-apple-system,sans-serif; background:#121212;
         color:#fff; display:flex; align-items:center; justify-content:center; height:100vh; }}
  .card {{ text-align:center; padding:48px; background:#181818; border-radius:24px;
           box-shadow:0 8px 40px rgba(0,0,0,.5); max-width:360px; }}
  .icon {{ font-size:64px; }}
  h1 {{ color:#1DB954; font-size:24px; margin:16px 0 8px; }}
  p {{ color:#b3b3b3; line-height:1.5; }}
</style>
</head>
<body>
<div class="card">
  <div class="icon">{icon}</div>
  <h1>{title}</h1>
  <p>{text}</p>
</div>
</body>
</html>"""


def progress_bar(done: int, total: int, width: int = 10) -> str:
    filled = int(width * done / total) if total else 0
    return "▰" * filled + "▱" * (width - filled)
