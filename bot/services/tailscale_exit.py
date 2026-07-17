"""Tailscale exit node orqali uy (residential) IP'dan chiqish — cookie'siz yechim.

YouTube Railway kabi data-markaz IP'laridan kelgan so'rovlarni "Sign in to
confirm you're not a bot" bilan rad etadi. Muammoning ildizi cookie'da EMAS —
chiqish IP'ining obro'sida: yt-dlp hujjatiga ko'ra cookie'siz "guest session"
soatiga ~300 video beradi, lekin faqat flagged bo'lmagan IP'dan. Shu sabab
chiqish IP'ini uy internetiga ko'chirsak, cookie umuman kerak bo'lmaydi
(yt-dlp #15865: `android_vr` ham endi flagged IP'da LOGIN_REQUIRED qaytaradi —
klient almashtirish bilan bu muammo yechilmaydi).

Tailscale userspace rejimda ishlaydi (TUN qurilmasi va NET_ADMIN kerak emas —
Railway konteynerida aynan shu shart) va localhost'da SOCKS5 proxy ochadi. Proxy
uydagi kompyuter (exit node) orqali yo'naltiriladi → YouTube uy IP'sini ko'radi.
Exit node userspace + SOCKS5 rejimida ishlaydi: tailscale#1970 PR #3448 bilan
yopilgan.

Og'ir ish Railway'da qoladi (ffmpeg, DB, Telegram) — uy kompyuteri faqat YouTube
baytlarini uzatadi (~4MB/trek).

Sozlash:
  1. Uy kompyuterida (doim yoqilgan turishi kerak):
       tailscale up --advertise-exit-node
     so'ng admin konsolda exit node'ni tasdiqlang.
  2. Railway env:
       TS_AUTHKEY=tskey-auth-...   (reusable auth key)
       TS_EXIT_NODE=uy-pc          (exit node hostname yoki 100.x.y.z IP)

Ikkalasi ham berilmasa modul jim o'tkazib yuboriladi va bot avvalgidek ishlaydi.
"""

import logging
import os
import shutil
import subprocess
import threading

log = logging.getLogger(__name__)

_SOCKS_PORT = os.getenv("TS_SOCKS_PORT", "1055").strip() or "1055"
_HOSTNAME = os.getenv("TS_HOSTNAME", "trackflow-bot").strip() or "trackflow-bot"
_IP_ECHO = "https://api.ipify.org"

_proc: subprocess.Popen | None = None


def _pump_output(proc: subprocess.Popen) -> None:
    """tailscaled outputini bot logiga oqizadi — crash sabablari ko'rinsin."""
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            log.info("tailscaled: %s", line)
    code = proc.wait()
    if code not in (0, None):
        log.warning("tailscaled to'xtadi (exit code %s)", code)


def _state_path() -> str:
    """State faylini volume'ga yozamiz — har deployda yangi qurilma yaralmasin."""
    if os.path.isdir("/data") and os.access("/data", os.W_OK):
        return "/data/tailscaled.state"
    return "/tmp/tailscaled.state"


def _egress_ip(proxy: str | None) -> str | None:
    """Chiqish IP'ini aniqlaydi. yt-dlp'ning O'Z tarmoq stegi orqali — yuklashda
    ishlatiladigan yo'l bilan bir xil bo'lishi uchun (socks5h ham shu yerda
    tekshiriladi)."""
    from yt_dlp import YoutubeDL

    opts = {"quiet": True, "no_warnings": True, "socket_timeout": 20}
    if proxy:
        opts["proxy"] = proxy
    try:
        with YoutubeDL(opts) as ydl:
            return ydl.urlopen(_IP_ECHO).read().decode("utf-8", "replace").strip()
    except Exception as e:
        log.warning("Chiqish IP'ini aniqlab bo'lmadi (proxy=%s): %s", proxy or "yo'q", e)
        return None


def start() -> bool:
    """tailscaled'ni userspace rejimda ko'taradi va YTDLP_PROXY'ni sozlaydi.

    Muvaffaqiyatli bo'lsa True qaytaradi. Proxy TEKSHIRUVDAN o'tmasa YTDLP_PROXY
    QO'YILMAYDI: yaroqsiz proxy hamma yuklashni buzadi, proxysiz esa YouTube
    yiqilsa ham SoundCloud fallback ishlaydi.
    """
    global _proc

    authkey = os.getenv("TS_AUTHKEY", "").strip()
    exit_node = os.getenv("TS_EXIT_NODE", "").strip()
    if not authkey or not exit_node:
        log.info(
            "Tailscale exit node sozlanmagan (TS_AUTHKEY/TS_EXIT_NODE yo'q) — "
            "YouTube to'g'ridan-to'g'ri Railway IP'dan so'raladi"
        )
        return False
    if os.getenv("YTDLP_PROXY", "").strip():
        log.info("YTDLP_PROXY qo'lda berilgan — Tailscale o'tkazib yuborildi")
        return False
    if not (shutil.which("tailscaled") and shutil.which("tailscale")):
        log.warning("tailscaled topilmadi — Tailscale exit node ishlatilmaydi")
        return False

    try:
        _proc = subprocess.Popen(
            [
                "tailscaled",
                "--tun=userspace-networking",
                f"--socks5-server=127.0.0.1:{_SOCKS_PORT}",
                f"--state={_state_path()}",
                "--socket=/tmp/tailscaled.sock",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        threading.Thread(target=_pump_output, args=(_proc,), daemon=True).start()
        log.info("tailscaled ishga tushdi (userspace, socks5 :%s)", _SOCKS_PORT)
    except Exception:
        log.exception("tailscaled'ni ishga tushirib bo'lmadi")
        _proc = None
        return False

    # `tailscale up` ulanish tugagunicha bloklaydi (--timeout bilan cheklaymiz).
    try:
        res = subprocess.run(
            [
                "tailscale", "--socket=/tmp/tailscaled.sock", "up",
                f"--authkey={authkey}",
                f"--exit-node={exit_node}",
                f"--hostname={_HOSTNAME}",
                "--accept-dns=false",
                "--timeout=60s",
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        log.error("`tailscale up` 90s ichida ulanmadi — exit node ishlatilmaydi")
        stop()
        return False
    if res.returncode != 0:
        # Eng ko'p uchraydigan sabab: exit node oflayn yoki admin konsolda
        # tasdiqlanmagan ("--advertise-exit-node" + approve).
        log.error(
            "`tailscale up` yiqildi (%s): %s",
            res.returncode, (res.stderr or res.stdout or "").strip()[:400],
        )
        stop()
        return False

    # socks5h — DNS'ni ham exit node hal qiladi, ya'ni googlevideo IP'si uy
    # geografiyasiga mos tanlanadi (socks5 bo'lsa DNS Railway'da hal bo'lardi).
    proxy = f"socks5h://127.0.0.1:{_SOCKS_PORT}"
    direct_ip = _egress_ip(None)
    exit_ip = _egress_ip(proxy)

    if not exit_ip:
        log.error(
            "SOCKS5 proxy javob bermadi — YTDLP_PROXY qo'yilmaydi (proxysiz davom)"
        )
        stop()
        return False
    if direct_ip and exit_ip == direct_ip:
        log.error(
            "Trafik exit node'ga YO'NALMAYAPTI (proxy IP = Railway IP = %s). "
            "Uy kompyuterida `tailscale up --advertise-exit-node` va admin "
            "konsolda tasdiqlash tekshiring — YTDLP_PROXY qo'yilmaydi.",
            direct_ip,
        )
        stop()
        return False

    os.environ["YTDLP_PROXY"] = proxy
    log.info(
        "Tailscale exit node FAOL: YouTube endi %s IP'sini ko'radi "
        "(Railway IP: %s) — cookie kerak emas",
        exit_ip, direct_ip or "noma'lum",
    )
    return True


def stop() -> None:
    global _proc
    if _proc is not None:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _proc.kill()
        _proc = None
