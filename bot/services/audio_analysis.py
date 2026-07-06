"""Lokal MIR (Music Information Retrieval) — 30s preview'lardan audio-vektor.

Deezer/iTunes 30 soniyalik preview MP3'ni ffmpeg bilan PCM'ga ochib, numpy bilan
trekning *qanday eshitilishini* tavsiflovchi ixcham vektor hisoblaydi:

  • temp (BPM) + puls aniqligi — onset-fluks avtokorrelyatsiyasi
  • energiya (RMS dB) + dinamika — balandlik va uning o'zgaruvchanligi
  • yorqinlik — spektral markaz (centroid) va rolloff
  • tembr — 40 polosali log-mel spektr (o'rtacha + std) → 80 o'lchamli embedding
  • garmoniya — 12 pog'onali chroma profili

Hisoblash bir trek uchun ~0.3-0.8s (yuklab olish bilan ~1s), natija JSON ko'rinishida
SQLite keshiga yoziladi — har trek umrida bir marta tahlil qilinadi.
"""

import asyncio
import logging
import math
import subprocess
from dataclasses import dataclass, field

import aiohttp
import numpy as np

log = logging.getLogger(__name__)

SR = 22050          # namuna chastotasi (mono)
N_FFT = 2048
HOP = 512
N_MELS = 40
_FPS = SR / HOP     # kadr/soniya (onset envelope uchun)

_MAX_PREVIEW = 3 * 1024 * 1024   # 3 MB dan katta preview — shubhali, o'tkazamiz
_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=12)
_EPS = 1e-10


@dataclass
class AudioVector:
    """Trekning sonik profili — barcha maydonlar taqqoslash uchun yetarli."""
    bpm: float = 0.0
    pulse: float = 0.0        # temp aniqligi 0..1 (ACF cho'qqisi)
    energy_db: float = 0.0    # o'rtacha RMS, dB (odatda -35..-5)
    dynamics: float = 0.0     # RMS dB std — dinamik diapazon
    centroid: float = 0.0     # spektral markaz, Hz
    rolloff: float = 0.0      # 85% energiya chegarasi, Hz
    flatness: float = 0.0     # spektral tekislik (log o'rtacha)
    zcr: float = 0.0          # nol kesish tezligi
    mel: list[float] = field(default_factory=list)     # 80 = 40 mean + 40 std (markazlashgan, L2=1)
    chroma: list[float] = field(default_factory=list)  # 12, L2=1

    def to_dict(self) -> dict:
        return {
            "bpm": round(self.bpm, 1), "pulse": round(self.pulse, 3),
            "energy_db": round(self.energy_db, 2), "dynamics": round(self.dynamics, 2),
            "centroid": round(self.centroid, 1), "rolloff": round(self.rolloff, 1),
            "flatness": round(self.flatness, 4), "zcr": round(self.zcr, 4),
            "mel": [round(v, 4) for v in self.mel],
            "chroma": [round(v, 4) for v in self.chroma],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AudioVector":
        return cls(
            bpm=float(d.get("bpm") or 0), pulse=float(d.get("pulse") or 0),
            energy_db=float(d.get("energy_db") or 0), dynamics=float(d.get("dynamics") or 0),
            centroid=float(d.get("centroid") or 0), rolloff=float(d.get("rolloff") or 0),
            flatness=float(d.get("flatness") or 0), zcr=float(d.get("zcr") or 0),
            mel=list(d.get("mel") or []), chroma=list(d.get("chroma") or []),
        )


# ─── Mel filterbank (librosasiz, standart uchburchak filtrlar) ────────────────

def _hz_to_mel(f: float) -> float:
    return 2595.0 * math.log10(1.0 + f / 700.0)


def _mel_to_hz(m: np.ndarray) -> np.ndarray:
    return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


def _mel_filterbank(n_mels: int, n_fft: int, sr: int, fmin: float = 30.0, fmax: float = 8000.0) -> np.ndarray:
    mels = np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2)
    hz = _mel_to_hz(mels)
    bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for i in range(n_mels):
        left, center, right = bins[i], bins[i + 1], bins[i + 2]
        center = max(center, left + 1)
        right = max(right, center + 1)
        fb[i, left:center] = (np.arange(left, center) - left) / (center - left)
        fb[i, center:right] = (right - np.arange(center, right)) / (right - center)
    return fb


_MEL_FB = _mel_filterbank(N_MELS, N_FFT, SR)
_FREQS = np.fft.rfftfreq(N_FFT, 1.0 / SR)

# Chroma uchun: har FFT bin → pitch-class (55Hz..5kHz oralig'ida)
_CHROMA_MASK = (_FREQS > 55.0) & (_FREQS < 5000.0)
_PITCH_CLASS = np.zeros(len(_FREQS), dtype=np.int64)
_PITCH_CLASS[_CHROMA_MASK] = (
    np.round(12.0 * np.log2(_FREQS[_CHROMA_MASK] / 440.0)).astype(np.int64) % 12
)


# ─── PCM dekodlash (ffmpeg) ───────────────────────────────────────────────────

def _decode(data: bytes) -> np.ndarray | None:
    """MP3/M4A baytlar → float32 mono PCM (SR). ffmpeg PATH'da bo'lishi shart
    (bot allaqachon yuklab olish va effektlar uchun ffmpeg'ga tayanadi)."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", "pipe:0",
             "-f", "f32le", "-ac", "1", "-ar", str(SR), "pipe:1"],
            input=data, capture_output=True, timeout=25,
        )
    except Exception:
        log.warning("ffmpeg dekodlash xatosi", exc_info=True)
        return None
    if proc.returncode != 0 or len(proc.stdout) < SR * 4 * 3:  # kamida 3 soniya
        return None
    return np.frombuffer(proc.stdout, dtype=np.float32)


# ─── Asosiy tahlil ────────────────────────────────────────────────────────────

def _estimate_tempo(logmel: np.ndarray) -> tuple[float, float]:
    """Onset-fluks avtokorrelyatsiyasi orqali (bpm, puls aniqligi 0..1)."""
    flux = np.diff(logmel, axis=1)
    onset = np.clip(flux, 0.0, None).sum(axis=0)
    if onset.size < int(_FPS * 4):  # < 4 soniya — temp ishonchsiz
        return 0.0, 0.0
    win = np.hanning(9)
    onset = np.convolve(onset, win / win.sum(), mode="same")
    onset = onset - onset.mean()

    acf = np.correlate(onset, onset, mode="full")[onset.size - 1:]
    if acf[0] <= 0:
        return 0.0, 0.0
    acf = acf / acf[0]

    lag_min = max(2, int(round(60.0 * _FPS / 200.0)))   # 200 BPM
    lag_max = min(acf.size - 1, int(round(60.0 * _FPS / 60.0)))  # 60 BPM
    if lag_max <= lag_min:
        return 0.0, 0.0

    best_bpm, best_score, best_acf = 0.0, -1.0, 0.0
    for lag in range(lag_min, lag_max + 1):
        bpm = 60.0 * _FPS / lag
        # 120 BPM atrofidagi log-normal prior (librosa uslubida)
        prior = math.exp(-0.5 * (math.log2(bpm / 120.0) / 0.9) ** 2)
        score = acf[lag] * prior
        if score > best_score:
            best_bpm, best_score, best_acf = bpm, score, acf[lag]
    return best_bpm, float(np.clip(best_acf, 0.0, 1.0))


def analyze_bytes(data: bytes) -> AudioVector | None:
    """Preview baytlaridan AudioVector. Xato/sukut bo'lsa None."""
    x = _decode(data)
    if x is None or x.size < N_FFT * 4:
        return None
    peak = float(np.abs(x).max())
    if peak < 1e-4:  # amalda sukunat
        return None

    n_frames = 1 + (x.size - N_FFT) // HOP
    n_frames = min(n_frames, int(_FPS * 32))  # xavfsizlik: ≤ 32 soniya
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = x[idx]

    rms = np.sqrt(np.mean(frames * frames, axis=1) + _EPS)
    rms_db = 20.0 * np.log10(rms + _EPS)
    energy_db = float(20.0 * math.log10(float(rms.mean()) + _EPS))
    dynamics = float(np.clip(rms_db.std(), 0.0, 20.0))

    window = np.hanning(N_FFT).astype(np.float32)
    S = np.abs(np.fft.rfft(frames * window, axis=1)).astype(np.float32)  # (n, bins)
    power = S * S

    # Faqat "jonli" kadrlar bo'yicha spektral statistikalar (sukut kadrlarini tashlaymiz)
    alive = rms > 0.1 * float(rms.max())
    Sa = S[alive] if alive.any() else S

    ssum = Sa.sum(axis=1) + _EPS
    centroid = float((Sa @ _FREQS / ssum).mean())
    cum = np.cumsum(Sa, axis=1)
    roll_idx = np.argmax(cum >= 0.85 * cum[:, -1:], axis=1)
    rolloff = float(_FREQS[roll_idx].mean())
    pw = power[alive] if alive.any() else power
    flatness = float(np.exp(np.mean(np.log(pw + _EPS), axis=1)).mean() / (pw.mean(axis=1).mean() + _EPS))
    zcr = float(np.mean(np.abs(np.diff(np.signbit(x).astype(np.int8)))) * SR / 2.0)

    # Tembr: log-mel mean+std, markazlashtirilib L2 normallashadi (balandlikka bog'liqmas)
    mel = _MEL_FB @ power.T                      # (n_mels, n)
    logmel = np.log(mel + 1e-8)
    mm = logmel.mean(axis=1)
    ms = logmel.std(axis=1)
    mm = mm - mm.mean()
    ms = ms - ms.mean()
    timbre = np.concatenate([mm, ms])
    norm = float(np.linalg.norm(timbre))
    timbre = timbre / norm if norm > 0 else timbre

    # Chroma: pitch-class bo'yicha magnitudalar yig'indisi
    chroma = np.zeros(12, dtype=np.float64)
    masked = Sa[:, _CHROMA_MASK].mean(axis=0)
    np.add.at(chroma, _PITCH_CLASS[_CHROMA_MASK], masked)
    cn = float(np.linalg.norm(chroma))
    chroma = chroma / cn if cn > 0 else chroma

    bpm, pulse = _estimate_tempo(logmel)

    return AudioVector(
        bpm=bpm, pulse=pulse, energy_db=energy_db, dynamics=dynamics,
        centroid=centroid, rolloff=rolloff, flatness=flatness, zcr=zcr,
        mel=[float(v) for v in timbre], chroma=[float(v) for v in chroma],
    )


async def analyze_url(session: aiohttp.ClientSession, url: str) -> AudioVector | None:
    """Preview URL → AudioVector (yuklab olish + thread'da DSP)."""
    if not url:
        return None
    try:
        async with session.get(url, timeout=_FETCH_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            if resp.content_length and resp.content_length > _MAX_PREVIEW:
                return None
            data = await resp.read()
        if not data or len(data) > _MAX_PREVIEW:
            return None
    except Exception:
        return None
    return await asyncio.to_thread(analyze_bytes, data)


# ─── O'xshashlik ──────────────────────────────────────────────────────────────

def _cos(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    va, vb = np.asarray(a), np.asarray(b)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na == 0 or nb == 0:
        return 0.0
    return float(va @ vb / (na * nb))


def similarity(a: AudioVector, b: AudioVector) -> float:
    """Ikki audio-vektor orasidagi umumiy sonik o'xshashlik 0..1.

    Har signal mavjudligi bo'yicha normallashadi (bpm topilmagan bo'lishi mumkin).
    """
    parts: list[tuple[float, float]] = []

    if a.bpm > 0 and b.bpm > 0:
        d = abs(math.log2(a.bpm / b.bpm))
        d = min(d, abs(d - 1.0))  # yarim/ikki barobar temp ekvivalent
        parts.append((0.22, math.exp(-((d / 0.13) ** 2))))

    if a.energy_db and b.energy_db:
        parts.append((0.13, math.exp(-((a.energy_db - b.energy_db) / 6.0) ** 2)))

    if a.centroid > 0 and b.centroid > 0:
        d = abs(math.log2(a.centroid / b.centroid))
        parts.append((0.13, math.exp(-((d / 0.40) ** 2))))

    if a.mel and b.mel:
        # markazlashgan vektorlar kosinusi: begona ~0..0.35, o'xshash ~0.55+
        t = (_cos(a.mel, b.mel) - 0.05) / 0.75
        parts.append((0.36, float(np.clip(t, 0.0, 1.0))))

    if a.chroma and b.chroma:
        c = (_cos(a.chroma, b.chroma) - 0.50) / 0.50
        parts.append((0.16, float(np.clip(c, 0.0, 1.0))))

    if not parts:
        return 0.0
    wsum = sum(w for w, _ in parts)
    return sum(w * s for w, s in parts) / wsum
