"""Production-grade admin control panel — Telegram orqali to'liq boshqaruv.

Modullar:
- roles     — rollar va ruxsatlar (super / admin / moderator)
- access    — admin tekshiruvi, ban enforcement, maintenance
- repo      — admin DB so'rovlari (ban, settings, stats, audit, broadcast)
- settings_store — bot_settings uchun keshli qatlam (middleware'да arzon)
- audit     — sezgir amallar uchun audit izi
- logbuf    — Logs bo'limi uchun in-memory halqa bufer log handler
- keyboards — admin inline klaviaturalari
- text      — admin panel matnlari (ingliz, egaga)
- dashboard — asosiy router (barcha bo'limlar)
- users     — foydalanuvchi boshqaruvi (qidiruv/profil/ban/xabar)
- broadcast — professional broadcast dvigateli
"""
