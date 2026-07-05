# 🎧 Spotify Downloader Bot

Spotify havolalari orqali musiqalarni **maksimal tezlikda** topib yuboradigan Telegram bot.

## Imkoniyatlar

- 🔗 **Havola yuborish** — trek, albom, playlist, ijrochi havolalarini avtomatik aniqlaydi
- 🔍 **Matnli qidiruv** — qo'shiq nomini yozing, o'zi topadi
- ❤️ **Liked Songs** — Spotify hisobingizni ulab, sevimli qo'shiqlaringizni to'liq yuklab oling
- ⚡ **file_id kesh** — bir marta yuklab olingan trek keyingi safar **bir soniyada** yuboriladi
- 🚀 **Parallel yuklab olish** — albom/playlist 3 ta trekdan bir vaqtda qayta ishlanadi
- 🏷 **To'liq metadata** — ID3 teglar, albom muqovasi, davomiylik
- ⚙️ Sifat tanlash (128/320 kbps), tarix, progress-bar, bekor qilish tugmasi

> **Eslatma:** Spotify audio faylni to'g'ridan-to'g'ri bermaydi. Bot Spotify'dan metadata oladi,
> audioni esa YouTube Music'dan eng mos variantini topib yuklab oladi (spotdl usuli).
> Bot shaxsiy foydalanish uchun mo'ljallangan.

> **Muhim (2025 o'zgarishi):** Spotify endi Web API ilovalari uchun ilova egasining hisobida
> **Premium** obuna talab qiladi. Premium bo'lmasa ham bot ishlayveradi — avtomatik **embed
> rejimga** o'tadi (ochiq open.spotify.com/embed sahifalaridan metadata oladi). Embed rejim
> cheklovlari: playlist'dan ~50 trekgacha olinadi, matn qidiruv YouTube Music orqali bajariladi,
> **Liked Songs esa ishlamaydi** (bunga rasmiy API + Premium shart).

## 1. Telegram bot token olish

1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing
2. `/newbot` → nom va username tanlang
3. Berilgan tokenni `.env` fayliga `BOT_TOKEN=` sifatida yozing

## 2. Spotify API kalitlarini olish

1. [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) ga kiring (oddiy Spotify hisobingiz bilan)
2. **Create app** tugmasini bosing:
   - **App name / description** — istalgan nom
   - **Redirect URI** — Railway'dagi domeningiz: `https://<app-nomi>.up.railway.app/callback`
     (lokal test uchun `http://localhost:8080/callback` ham qo'shib qo'ying)
   - **Which API/SDKs are you planning to use?** — Web API
3. **Settings** dan **Client ID** va **Client Secret** ni ko'chirib oling
4. Ularni `.env` ga yozing:
   ```
   SPOTIFY_CLIENT_ID=...
   SPOTIFY_CLIENT_SECRET=...
   ```

## 3. Lokal ishga tushirish (Windows)

```powershell
# FFmpeg o'rnatish (bir marta)
winget install ffmpeg

# Loyiha papkasida
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# .env faylini tayyorlash
copy .env.example .env
# .env ni ochib BOT_TOKEN va Spotify kalitlarini kiriting

# Ishga tushirish
python -m bot.main
```

## 4. Railway'ga deploy qilish

1. Loyihani GitHub'ga push qiling (`.env` **hech qachon** push qilinmasin — `.gitignore` da bor)
2. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. **Variables** bo'limida quyidagilarni qo'shing:

   | O'zgaruvchi | Qiymat |
   |---|---|
   | `BOT_TOKEN` | BotFather'dan olingan token |
   | `SPOTIFY_CLIENT_ID` | Spotify dashboard'dan |
   | `SPOTIFY_CLIENT_SECRET` | Spotify dashboard'dan |
   | `DB_PATH` | `/data/bot.db` |
   | `ADMIN_ID` | Telegram ID'ingiz (ixtiyoriy, /stats uchun) |

4. **Settings → Networking → Generate Domain** — port so'ralsa `8080` kiriting
5. **Volume qo'shing**: xizmat ustiga o'ng tugma → **Attach Volume** → mount path: `/data`
   (kesh va foydalanuvchi ma'lumotlari redeploy'da saqlanib qoladi)
6. Spotify dashboard'dagi **Redirect URI** ni Railway domeningizga moslang:
   `https://<domeningiz>/callback`

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `/start` | Asosiy menyu |
| `/liked` | Liked Songs yuklab olish |
| `/settings` | Sifat sozlamalari (128/320 kbps) |
| `/history` | Oxirgi yuklab olinganlar |
| `/stats` | Statistika (faqat admin) |

## Arxitektura

```
bot/
├── main.py          # entry: polling + OAuth web-server
├── config.py        # .env sozlamalari
├── texts.py         # barcha matnlar (UZ)
├── keyboards.py     # inline tugmalar
├── handlers/        # start, links, search, library, settings
├── services/
│   ├── spotify.py   # async Spotify Web API klienti (metadata, OAuth, Liked)
│   ├── matcher.py   # YouTube'dan eng mos audio topish (yt-dlp qidiruvi)
│   ├── downloader.py# yt-dlp → MP3 → ID3 teglar + muqova
│   └── queue.py     # kesh, parallel yuklash, progress, bekor qilish
├── db/              # SQLite: userlar, file_id kesh, tarix, tokenlar
└── web/oauth.py     # Spotify OAuth callback sahifasi
```
