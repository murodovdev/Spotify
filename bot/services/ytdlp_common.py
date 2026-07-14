"""yt-dlp uchun umumiy sozlamalar: player_client tanlash.

yt-dlp 2026.07+ YouTube signature/n-challenge uchun JS runtime (deno) talab
qiladi. `android_vr` klienti PO token yoki cookies'siz barcha formatlarni
(m4a, opus, video) beradi — boshqa klientlar SABR-only yoki cookies'ga
bog'liq bo'lib qolgan.
"""

import logging

log = logging.getLogger(__name__)

# android_vr — yagona ishonchli klient (2026.07+ deno bilan):
#   cookies BERILSA yt-dlp uni skip qiladi ("does not support cookies")
#   web — cookies bilan ham SABR-only (URL bermaydi)
_CLIENTS = ["android_vr"]


def apply(opts: dict) -> dict:
    """yt-dlp opts'ga player_client sozlamalarini qo'shadi (idempotent)."""
    ea = opts.setdefault("extractor_args", {})
    ea.setdefault("youtube", {}).setdefault("player_client", list(_CLIENTS))
    return opts
