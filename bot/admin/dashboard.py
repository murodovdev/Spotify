"""Admin dashboard — asosiy router: /admin, home va barcha bo'limlar.

FSM-og'ir oqimlar (foydalanuvchi qidiruv/xabar, broadcast compose) users.py va
broadcast.py да. Bu modul dashboard + o'qish bo'limlari + oddiy amallarни ushlaydi.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.admin import keyboards, logbuf, repo, roles, settings_store
from bot.admin.access import AdminFilter, ensure_perm
from bot.admin.roles import Perm
from bot.config import settings as cfg
from bot.db import maintenance as db_maint
from bot.db import repo as core_repo
from bot.db.database import db, db_path
from bot.services.queue import manager

log = logging.getLogger(__name__)

router = Router(name="admin_dashboard")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

HR = "━━━━━━━━━━━━━━━━━━━━"


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _ago(ts: float) -> str:
    if not ts:
        return "never"
    d = time.time() - ts
    if d < 60:
        return f"{int(d)}s ago"
    if d < 3600:
        return f"{int(d / 60)}m ago"
    if d < 86400:
        return f"{int(d / 3600)}h ago"
    return f"{int(d / 86400)}d ago"


async def _edit(cq: CallbackQuery, text: str, kb) -> None:
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except TelegramBadRequest as e:
        # "message is not modified" — Refresh bosilганда kontent bir xil bo'lsa;
        # jim o'tамиз (aks holda pastdaги answer dublikat xabar yaratardi).
        if "not modified" in str(e).lower():
            return
        try:
            await cq.message.answer(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
    except Exception:
        try:
            await cq.message.answer(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass


# ─────────────────────────────── Home ───────────────────────────────────────

async def _home_text(role: str) -> str:
    total = await repo.count_users()
    today = await repo.active_since(time.time() - 86400)
    dls_today = await repo.daily_sum("downloads", 1)
    maint = "🛠 <b>ON</b>" if settings_store.is_maintenance() else "off"
    return (
        f"🎛 <b>Admin Control Panel</b>\n{HR}\n"
        f"Signed in as <b>{roles.ROLE_LABELS.get(role, role)}</b>\n\n"
        f"👥 Users: <b>{total}</b>   ·   🟢 Active 24h: <b>{today}</b>\n"
        f"⬇️ Downloads today: <b>{dls_today}</b>\n"
        f"🛠 Maintenance: {maint}\n\n"
        f"<i>Select a section:</i>"
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, role: str, state: FSMContext) -> None:
    await state.clear()  # yarim qolgan oqimni (ban/dm/qidiruv…) tozalaymiz
    await message.answer(await _home_text(role), reply_markup=keyboards.dashboard(role))


@router.callback_query(F.data == "adm:home")
async def cb_home(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    await state.clear()
    await cq.answer()
    await _edit(cq, await _home_text(role), keyboards.dashboard(role))


# ─────────────────────────── Section dispatch ───────────────────────────────

@router.callback_query(F.data.startswith("adm:sec:"))
async def cb_section(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    # Har qanday bo'limга o'tish yarim qolgan FSM oqimini tozalaydi — aks holda
    # "Cancel" (bo'limga qaytadi) holatни tozalamas edi va keyingi yozilган matn
    # oldingi nishonга (masalan ban sababi sifatida) qo'llanardi.
    await state.clear()
    key = cq.data.split(":", 2)[2]
    render = _RENDERERS.get(key)
    if render is None:
        await cq.answer("Unknown section")
        return
    # ruxsat tekshiruvi
    perm = dict((k, p) for _, k, p in keyboards.SECTIONS).get(key)
    if perm and not await ensure_perm(cq, role, perm):
        return
    await cq.answer()
    try:
        text, kb = await render(role)
    except Exception:
        log.exception("Admin section %s render failed", key)
        await cq.answer("⚠️ Couldn't load this section — check Logs.", show_alert=True)
        return
    await _edit(cq, text, kb)


# ── Analytics ────────────────────────────────────────────────────────────────

async def _sec_analytics(role: str):
    total = await repo.count_users()
    a_day = await repo.active_since(time.time() - 86400)
    a_week = await repo.active_since(time.time() - 7 * 86400)
    a_month = await repo.active_since(time.time() - 30 * 86400)
    core = await core_repo.get_stats()
    dl_today = await repo.daily_sum("downloads", 1)
    dl_week = await repo.daily_sum("downloads", 7)
    rec_today = await repo.daily_sum("recognitions", 1)
    top = await repo.top_songs("downloads", 5)
    top_txt = "\n".join(
        f"  {i}. {html.escape((r['artist'] or '') + ' — ' + (r['title'] or ''))[:44]} ({r['n']})"
        for i, r in enumerate(top, 1)
    ) or "  —"
    return (
        f"📊 <b>Analytics</b>\n{HR}\n"
        f"👥 Total users: <b>{total}</b>\n"
        f"🟢 Active — 24h <b>{a_day}</b> · 7d <b>{a_week}</b> · 30d <b>{a_month}</b>\n\n"
        f"⬇️ Downloads — today <b>{dl_today}</b> · 7d <b>{dl_week}</b> · all <b>{core['downloads']}</b>\n"
        f"⚡ Cache hits: <b>{core['cache_hits']}</b> (rate <b>{core['hit_rate']}%</b>)\n"
        f"🎧 Recognitions today: <b>{rec_today}</b>\n"
        f"💾 Cached tracks: <b>{core['cached']}</b>\n\n"
        f"🔥 <b>Top downloaded</b>\n{top_txt}"
    ), keyboards.simple_back()


# ── Music management ─────────────────────────────────────────────────────────

async def _sec_music(role: str):
    top_dl = await repo.top_songs("downloads", 5)
    top_sr = await repo.top_songs("searches", 5)
    top_rc = await repo.top_songs("recognitions", 5)
    failed = await repo.recent_failed("search", 6)
    fail_cnt = await repo.count_failed("search", time.time() - 86400)

    def fmt(rows):
        return "\n".join(
            f"  • {html.escape((r['artist'] or '') + ' — ' + (r['title'] or ''))[:42]} ({r['n']})"
            for r in rows
        ) or "  —"

    fail_txt = "\n".join(f"  • {html.escape(r['query'] or '')[:44]}" for r in failed) or "  —"
    return (
        f"🎵 <b>Music Management</b>\n{HR}\n"
        f"🔥 <b>Trending (downloads)</b>\n{fmt(top_dl)}\n\n"
        f"🔍 <b>Most searched</b>\n{fmt(top_sr)}\n\n"
        f"🎧 <b>Most recognized</b>\n{fmt(top_rc)}\n\n"
        f"❌ <b>Failed searches (24h): {fail_cnt}</b>\n{fail_txt}"
    ), keyboards.music_panel()


# ── Language ─────────────────────────────────────────────────────────────────

async def _sec_lang(role: str):
    rows = await repo.lang_counts()
    total = sum(r["n"] for r in rows) or 1
    lines = []
    for r in rows:
        pct = round(r["n"] * 100 / total)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        lines.append(f"  <code>{r['lang']:<4}</code> {bar} {r['n']} ({pct}%)")
    return (
        f"🌐 <b>Language Distribution</b>\n{HR}\n" + "\n".join(lines)
    ), keyboards.simple_back()


# ── Moderation ───────────────────────────────────────────────────────────────

async def _sec_mod(role: str, offset: int = 0):
    rows = await repo.list_bans(offset, 8)
    total = await repo.count_bans()
    lines = []
    for r in rows:
        kind = "🚫 Ban" if r["kind"] == "ban" else "⏳ Suspend"
        until = "permanent" if not r["until"] else _ago(r["until"]).replace("ago", "left") \
            if r["until"] > time.time() else "expired"
        reason = html.escape(r["reason"] or "—")[:40]
        lines.append(f"  {kind} · <code>{r['user_id']}</code> · {until}\n     {reason}")
    body = "\n".join(lines) or "  No active bans."
    return (
        f"🚫 <b>Moderation</b> — {total} blocked\n{HR}\n{body}\n\n"
        f"<i>Tap an entry to open the profile.</i>"
    ), keyboards.moderation_home(rows, offset, offset + 8 < total)


# ── Database ─────────────────────────────────────────────────────────────────

async def _sec_db(role: str):
    size = await repo.db_size_bytes()
    tables = await repo.table_sizes()
    path = db_path()
    lines = "\n".join(f"  <code>{t:<15}</code> {n:>8}" for t, n in tables[:12])
    warn = "\n⚠️ <b>DB &gt; 4 GB</b>" if size > 4 * 1024**3 else ""
    return (
        f"💾 <b>Database Health</b>\n{HR}\n"
        f"📦 Size: <b>{_human_bytes(size)}</b>{warn}\n"
        f"📁 <code>{html.escape(path)}</code>\n\n"
        f"<b>Table rows</b>\n{lines}"
    ), keyboards.database_panel()


# ── Performance ──────────────────────────────────────────────────────────────

async def _sec_perf(role: str):
    lines = [f"📈 <b>Performance</b>\n{HR}"]
    try:
        import psutil  # type: ignore

        # cpu_percent(interval=…) bloklaydi — bitta event loopда butun botни
        # muzlatib qo'yardi. Threadга chiqaramiz.
        cpu = await asyncio.to_thread(psutil.cpu_percent, 0.3)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(os.path.dirname(db_path()) or ".")
        proc = psutil.Process()
        rss = proc.memory_info().rss

        def flag(v):
            return " ⚠️" if v >= 85 else ""

        lines += [
            f"🖥 CPU: <b>{cpu:.0f}%</b>{flag(cpu)}",
            f"🧠 RAM: <b>{mem.percent:.0f}%</b> ({_human_bytes(mem.used)}/{_human_bytes(mem.total)}){flag(mem.percent)}",
            f"💽 Disk: <b>{disk.percent:.0f}%</b> ({_human_bytes(disk.free)} free){flag(disk.percent)}",
            f"📦 Bot RSS: <b>{_human_bytes(rss)}</b>",
        ]
    except ImportError:
        try:
            la = os.getloadavg()
            lines.append(f"🖥 Load avg: <b>{la[0]:.2f} {la[1]:.2f} {la[2]:.2f}</b>")
        except (AttributeError, OSError):
            lines.append("🖥 <i>psutil not installed — limited metrics.</i>")
        st = os.statvfs(os.path.dirname(db_path()) or ".") if hasattr(os, "statvfs") else None
        if st:
            free = st.f_bavail * st.f_frsize
            lines.append(f"💽 Disk free: <b>{_human_bytes(free)}</b>")
    lines.append(f"\n📂 Active download jobs: <b>{len(manager.active)}</b>")
    return "\n".join(lines), keyboards.simple_back()


# ── Queue ────────────────────────────────────────────────────────────────────

async def _sec_queue(role: str):
    active = manager.active
    lines = []
    for uid, job in list(active.items())[:15]:
        state = "🛑 cancelling" if job.cancelled else "⏳ running"
        lines.append(f"  <code>{uid}</code> · {state}")
    body = "\n".join(lines) or "  No active jobs."
    return (
        f"📂 <b>Queue Manager</b>\n{HR}\n"
        f"Active collection jobs: <b>{len(active)}</b>\n{body}\n\n"
        f"<i>Downloads run per-user with windowed concurrency. Use a user's "
        f"profile or /admin → Users to inspect.</i>"
    ), keyboards.simple_back()


# ── System ───────────────────────────────────────────────────────────────────

async def _sec_sys(role: str):
    admins = await repo.list_admins()
    can = roles.has_perm(role, Perm.MANAGE_ADMINS)
    lines = [f"  👑 <code>{cfg.admin_id}</code> · Super Admin (config)"] if cfg.admin_id else []
    for r in admins:
        lines.append(f"  {roles.ROLE_LABELS.get(r['role'], r['role'])} · <code>{r['user_id']}</code>")
    body = "\n".join(lines) or "  —"
    return (
        f"🔧 <b>System Tools</b>\n{HR}\n"
        f"<b>Administrators</b>\n{body}\n\n"
        f"🐍 PID: <b>{os.getpid()}</b>\n"
        f"{'<i>Tap an admin to remove, or add a new one.</i>' if can else ''}"
    ), keyboards.system_panel(admins, can)


# ── Logs ─────────────────────────────────────────────────────────────────────

async def _logs_text(kind: str) -> str:
    if kind == "AUDIT":
        rows = await repo.recent_audit(15)
        body = "\n".join(
            f"  <code>{logbuf.fmt_ts(r['at'])}</code> <code>{r['admin_id']}</code> "
            f"{html.escape(r['action'])}"
            f"{(' → ' + html.escape(str(r['target']))) if r['target'] else ''}"
            for r in rows
        ) or "  No audit entries."
        return f"📜 <b>Audit Log</b>\n{HR}\n{body}"
    recs = logbuf.query(level=kind, limit=15)
    c = logbuf.counts()
    body = "\n".join(
        f"  <code>{logbuf.fmt_ts(r.ts)}</code> [{html.escape(r.logger)}]\n     {html.escape(r.msg)[:80]}"
        for r in recs
    ) or "  Clean — nothing logged."
    return f"📜 <b>Logs</b> · ⛔{c['ERROR']} ⚠️{c['WARNING']}\n{HR}\n{body}"


async def _sec_logs(role: str):
    return await _logs_text("ERROR"), keyboards.logs_panel("ERROR")


@router.callback_query(F.data.startswith("adm:log:"))
async def cb_logs_tab(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.VIEW_LOGS):
        return
    kind = cq.data.split(":", 2)[2]
    await cq.answer()
    await _edit(cq, await _logs_text(kind), keyboards.logs_panel(kind))


@router.callback_query(F.data.startswith("adm:mod:p:"))
async def cb_mod_page(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MODERATE):
        return
    offset = max(0, int(cq.data.rsplit(":", 1)[1]))
    await cq.answer()
    text, kb = await _sec_mod(role, offset)
    await _edit(cq, text, kb)


# ─────────────────────── Simple actions (non-FSM) ───────────────────────────

@router.callback_query(F.data == "adm:db:maint")
async def cb_db_maint(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_DB):
        return
    await cq.answer("Running maintenance…")
    try:
        await db_maint.run_once()
        await repo.add_audit(cq.from_user.id, "db_maintenance")
        note = "✅ Maintenance completed."
    except Exception as e:
        log.exception("Admin DB maintenance failed")
        note = f"❌ Failed: {html.escape(str(e))[:100]}"
    text, kb = await _sec_db(role)
    await _edit(cq, f"{text}\n\n{note}", kb)


@router.callback_query(F.data == "adm:db:check")
async def cb_db_check(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_DB):
        return
    await cq.answer("Checking…")
    ok = await repo.integrity_ok()
    note = "✅ Integrity: OK" if ok else "❌ Integrity check FAILED"
    text, kb = await _sec_db(role)
    await _edit(cq, f"{text}\n\n{note}", kb)


@router.callback_query(F.data == "adm:music:clearc")
async def cb_music_clear_confirm(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_MUSIC):
        return
    await cq.answer()
    await _edit(
        cq,
        f"🗑 <b>Clear metadata cache?</b>\n{HR}\n"
        f"This wipes the recommendation feature cache (<code>rec_features</code>). "
        f"It will be rebuilt on demand — safe, but the next few similar-song "
        f"lookups will be slower.",
        keyboards.confirm_action("adm:music:clearfeat", "sec:music", "🗑 Clear"),
    )


@router.callback_query(F.data == "adm:music:clearfeat")
async def cb_music_clear(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_MUSIC):
        return
    await cq.answer("Clearing…")
    await db().execute("DELETE FROM rec_features")
    await db().commit()
    await repo.add_audit(cq.from_user.id, "clear_metadata_cache")
    text, kb = await _sec_music(role)
    await _edit(cq, f"{text}\n\n✅ Metadata cache cleared.", kb)


# ── Settings toggles & edits ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:set:t:"))
async def cb_setting_toggle(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_SETTINGS):
        return
    key = cq.data.split(":", 3)[3]
    if key not in settings_store.BOOL_KEYS:
        await cq.answer("Not a toggle")
        return
    new = await settings_store.toggle(key)
    await repo.add_audit(cq.from_user.id, "setting_toggle", key, str(new))
    await cq.answer(f"{key} → {'ON' if new else 'OFF'}")
    text, _ = await _sec_settings(role)
    await _edit(cq, text, keyboards.settings_panel())


async def _sec_settings(role: str):
    dl = settings_store.get("download_limit")
    wl = settings_store.get("welcome_override")
    an = settings_store.get("announcement")
    return (
        f"⚙️ <b>Bot Settings</b>\n{HR}\n"
        f"Toggle features on/off. Changes apply immediately.\n\n"
        f"⬇️ Download limit/day: <b>{dl or '∞'}</b>\n"
        f"✏️ Welcome override: <b>{'set' if wl else 'default'}</b>\n"
        f"📣 Announcement: <b>{'active' if an else 'none'}</b>"
    ), keyboards.settings_panel()


# ── System: remove admin (super only) ────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:sys:rmc:"))
async def cb_sys_remove_confirm(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_ADMINS):
        return
    uid = int(cq.data.rsplit(":", 1)[1])
    await cq.answer()
    await _edit(
        cq,
        f"🗑 <b>Remove admin</b> <code>{uid}</code>?\n{HR}\n"
        f"They will immediately lose all panel access.",
        keyboards.confirm_action(f"adm:sys:rm:{uid}", "sec:sys", "🗑 Remove"),
    )


@router.callback_query(F.data.startswith("adm:sys:rm:"))
async def cb_sys_remove(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_ADMINS):
        return
    uid = int(cq.data.rsplit(":", 1)[1])
    await repo.remove_admin(uid)
    await repo.add_audit(cq.from_user.id, "remove_admin", str(uid))
    await cq.answer("Admin removed")
    text, kb = await _sec_sys(role)
    await _edit(cq, text, kb)


async def _sec_users(role: str):
    total = await repo.count_users()
    return (
        f"👥 <b>User Management</b>\n{HR}\n"
        f"Total users: <b>{total}</b>\n\n"
        f"🔍 Search a user by <b>ID</b>, <b>@username</b>, or name to view their "
        f"profile, stats, and moderation actions."
    ), keyboards.users_home()


async def _sec_broadcast(role: str):
    recent = await repo.recent_broadcasts(6)
    lines = []
    for r in recent:
        icon = {"done": "✅", "running": "🚀", "cancelled": "🛑",
                "failed": "❌", "pending": "⏳"}.get(r["status"], "•")
        lines.append(
            f"  {icon} #{r['id']} {r['kind']} · {r['sent']}/{r['total']} sent"
            f"{(' · ' + str(r['failed']) + ' failed') if r['failed'] else ''}"
        )
    body = "\n".join(lines) or "  No broadcasts yet."
    return (
        f"📢 <b>Broadcast</b>\n{HR}\n"
        f"Send text, photo, video, audio, voice, document or poll to all users.\n"
        f"You'll preview before sending.\n\n"
        f"<b>Recent</b>\n{body}"
    ), keyboards.broadcast_home()


_RENDERERS = {
    "users": _sec_users,
    "bc": _sec_broadcast,
    "an": _sec_analytics,
    "music": _sec_music,
    "lang": _sec_lang,
    "mod": _sec_mod,
    "db": _sec_db,
    "perf": _sec_perf,
    "queue": _sec_queue,
    "sys": _sec_sys,
    "logs": _sec_logs,
    "set": _sec_settings,
}
