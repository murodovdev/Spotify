"""FSM-og'ir admin oqimlari: foydalanuvchi qidiruv/profil/ban/xabar,
sozlama qiymati, admin qo'shish."""

from __future__ import annotations

import html
import logging
import time

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.admin import keyboards, repo, roles, settings_store
from bot.admin.access import AdminFilter, ensure_perm
from bot.admin.roles import Perm
from bot.admin.state import AdminFSM
from bot.db import repo as core_repo

log = logging.getLogger(__name__)

router = Router(name="admin_flows")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

HR = "━━━━━━━━━━━━━━━━━━━━"


async def _edit(cq: CallbackQuery, text: str, kb) -> None:
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await cq.message.answer(text, reply_markup=kb, disable_web_page_preview=True)


def _fmt_ts(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "—"


# ─────────────────────────── Foydalanuvchi profili ──────────────────────────

async def _profile(user_id: int) -> tuple[str, object] | None:
    u = await repo.get_user(user_id)
    if u is None:
        return None
    extras = await repo.user_extras(user_id)
    blocked, reason = await repo.is_blocked(user_id)
    ban = await repo.get_ban(user_id) if blocked else None
    is_admin = await repo.get_role(user_id)

    uname = f"@{u['username']}" if u["username"] else "—"
    name = html.escape(u["first_name"] or "—")
    status = "🟢 Active"
    if blocked:
        kind = "🚫 Banned" if ban and ban["kind"] == "ban" else "⏳ Suspended"
        until = "permanent" if not ban or not ban["until"] else _fmt_ts(ban["until"])
        status = f"{kind} · until {until}\n     └ {html.escape(reason or '—')}"

    text = (
        f"👤 <b>User Profile</b>\n{HR}\n"
        f"🆔 <code>{u['id']}</code>\n"
        f"👤 {name}   {html.escape(uname)}\n"
        f"🌐 Language: <b>{u['lang'] or '—'}</b>\n"
        f"🎧 Quality: <b>{u['quality']}</b>\n"
        f"📅 Joined: <b>{u['created_at']}</b>\n"
        f"🕐 Last active: <b>{_fmt_ts(u['last_active'])}</b>\n"
        f"⭐ Favorites: <b>{extras['favorites']}</b>\n"
        f"🔗 Spotify: <b>{'connected' if extras['connected'] else 'no'}</b>\n"
        f"{'🛡 Role: <b>' + roles.ROLE_LABELS.get(is_admin, is_admin) + '</b>' if is_admin else ''}\n"
        f"\n📌 Status: {status}"
    )
    return text, keyboards.user_profile(user_id, blocked)


# ─────────────────────────────── Qidiruv ────────────────────────────────────

@router.callback_query(F.data == "adm:u:search")
async def cb_user_search(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_USERS):
        return
    await state.set_state(AdminFSM.user_search)
    await cq.answer()
    await _edit(
        cq,
        f"🔍 <b>Search User</b>\n{HR}\nSend an <b>ID</b>, <b>@username</b> or name.",
        keyboards.cancel_only("sec:users"),
    )


@router.message(AdminFSM.user_search)
async def on_user_search(message: Message, role: str, state: FSMContext) -> None:
    if not roles.has_perm(role, Perm.MANAGE_USERS):
        await state.clear()
        return
    await state.clear()
    rows = await repo.find_users(message.text or "")
    if not rows:
        await message.answer("😔 No users found.", reply_markup=keyboards.users_home())
        return
    if len(rows) == 1:
        res = await _profile(rows[0]["id"])
        if res:
            await message.answer(res[0], reply_markup=res[1], disable_web_page_preview=True)
            return
    await message.answer(
        f"🔍 <b>{len(rows)} match(es)</b>\n{HR}\nSelect a user:",
        reply_markup=keyboards.users_results(rows),
    )


@router.callback_query(F.data.startswith("adm:u:v:"))
async def cb_user_view(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_USERS):
        return
    # Profilга qaytish yarim qolgan ban/dm oqimini tozalaydi (Cancel shu yerга
    # keladi) — aks holda keyingi matn oldingi nishonга qo'llanardi.
    await state.clear()
    user_id = int(cq.data.rsplit(":", 1)[1])
    res = await _profile(user_id)
    await cq.answer()
    if res is None:
        await _edit(cq, "😔 User not found.", keyboards.users_home())
        return
    await _edit(cq, res[0], res[1])


# ─────────────────────────────── Reset ──────────────────────────────────────

@router.callback_query(F.data.startswith("adm:u:rstc:"))
async def cb_user_reset_confirm(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_USERS):
        return
    user_id = int(cq.data.rsplit(":", 1)[1])
    await cq.answer()
    await _edit(
        cq,
        f"♻️ <b>Reset user</b> <code>{user_id}</code>?\n{HR}\n"
        f"Clears their language & quality settings and <b>deletes all their "
        f"favorites</b>. This cannot be undone.",
        keyboards.confirm_action(f"adm:u:reset:{user_id}", f"u:v:{user_id}", "♻️ Reset"),
    )


@router.callback_query(F.data.startswith("adm:u:reset:"))
async def cb_user_reset(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_USERS):
        return
    user_id = int(cq.data.rsplit(":", 1)[1])
    await repo.reset_user(user_id)
    core_repo.invalidate(user_id)
    await repo.add_audit(cq.from_user.id, "reset_user", str(user_id))
    await cq.answer("♻️ Settings reset", show_alert=True)
    res = await _profile(user_id)
    if res:
        await _edit(cq, res[0], res[1])


# ─────────────────────────────── Ban / Suspend ──────────────────────────────

@router.callback_query(F.data.startswith("adm:u:ban:"))
async def cb_user_ban(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.MODERATE):
        return
    user_id = int(cq.data.rsplit(":", 1)[1])
    if await repo.get_role(user_id) is not None:
        await cq.answer("⛔ This user is an admin — remove their role first.", show_alert=True)
        return
    await state.set_state(AdminFSM.ban_reason)
    await state.update_data(target=user_id, kind="ban", until=0)
    await cq.answer()
    await _edit(
        cq,
        f"🚫 <b>Ban user</b> <code>{user_id}</code>\n{HR}\n"
        f"Send a <b>reason</b> (or “-” for none).",
        keyboards.cancel_only(f"u:v:{user_id}"),
    )


@router.callback_query(F.data.startswith("adm:u:susp:"))
async def cb_user_suspend(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MODERATE):
        return
    user_id = int(cq.data.rsplit(":", 1)[1])
    if await repo.get_role(user_id) is not None:
        await cq.answer("⛔ This user is an admin — remove their role first.", show_alert=True)
        return
    until = time.time() + 86400
    await repo.set_ban(user_id, "suspend", "Temporary 24h suspension", until, cq.from_user.id)
    await repo.add_audit(cq.from_user.id, "suspend_user", str(user_id), "24h")
    await cq.answer("⏳ Suspended 24h", show_alert=True)
    res = await _profile(user_id)
    if res:
        await _edit(cq, res[0], res[1])


@router.message(AdminFSM.ban_reason)
async def on_ban_reason(message: Message, role: str, state: FSMContext) -> None:
    if not roles.has_perm(role, Perm.MODERATE):
        await state.clear()
        return
    data = await state.get_data()
    await state.clear()
    user_id = data["target"]
    reason = (message.text or "").strip()
    if reason.startswith("/"):
        # Buyruq — admin ban oqimidan chiqmoqchi; banlamaymiz.
        await message.answer("Ban cancelled.", reply_markup=keyboards.users_home())
        return
    if await repo.get_role(user_id) is not None:
        await message.answer("⛔ This user is an admin — remove their role first.",
                             reply_markup=keyboards.users_home())
        return
    reason = "" if reason == "-" else reason[:200]
    await repo.set_ban(user_id, data["kind"], reason or None, data["until"], message.from_user.id)
    await repo.add_audit(message.from_user.id, "ban_user", str(user_id), reason)
    res = await _profile(user_id)
    if res:
        await message.answer("🚫 User banned.\n\n" + res[0], reply_markup=res[1],
                             disable_web_page_preview=True)


@router.callback_query(F.data.startswith("adm:mod:unban:"))
async def cb_unban(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MODERATE):
        return
    user_id = int(cq.data.rsplit(":", 1)[1])
    await repo.unban(user_id)
    await repo.add_audit(cq.from_user.id, "unban_user", str(user_id))
    await cq.answer("✅ Unbanned", show_alert=True)
    res = await _profile(user_id)
    if res:
        await _edit(cq, res[0], res[1])


# ─────────────────────────── Foydalanuvchiga xabar ──────────────────────────

@router.callback_query(F.data.startswith("adm:u:dm:"))
async def cb_user_dm(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_USERS):
        return
    user_id = int(cq.data.rsplit(":", 1)[1])
    await state.set_state(AdminFSM.dm_text)
    await state.update_data(target=user_id)
    await cq.answer()
    await _edit(
        cq,
        f"✉️ <b>Message to</b> <code>{user_id}</code>\n{HR}\nSend the text now.",
        keyboards.cancel_only(f"u:v:{user_id}"),
    )


@router.message(AdminFSM.dm_text)
async def on_dm_text(message: Message, role: str, state: FSMContext, bot: Bot) -> None:
    if not roles.has_perm(role, Perm.MANAGE_USERS):
        await state.clear()
        return
    data = await state.get_data()
    await state.clear()
    user_id = data["target"]
    try:
        await bot.send_message(user_id, f"📩 <b>Message from admin</b>\n{HR}\n{message.html_text}")
        await repo.add_audit(message.from_user.id, "dm_user", str(user_id))
        note = "✅ Message delivered."
    except Exception as e:
        note = f"❌ Could not deliver: {html.escape(str(e))[:100]}"
    res = await _profile(user_id)
    if res:
        await message.answer(f"{note}\n\n" + res[0], reply_markup=res[1],
                             disable_web_page_preview=True)


# ─────────────────────────── Sozlama qiymatini tahrirlash ────────────────────

_SETTING_PROMPTS = {
    "download_limit": "Send the daily download limit (a number, 0 = unlimited).",
    "welcome_override": "Send the new welcome message (or “-” to use the default).",
    "announcement": "Send an announcement shown on /start (or “-” to clear).",
}


@router.callback_query(F.data.startswith("adm:set:e:"))
async def cb_setting_edit(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_SETTINGS):
        return
    key = cq.data.split(":", 3)[3]
    if key not in _SETTING_PROMPTS:
        await cq.answer("Unknown setting")
        return
    await state.set_state(AdminFSM.setting_value)
    await state.update_data(key=key)
    await cq.answer()
    await _edit(cq, f"✏️ <b>{key}</b>\n{HR}\n{_SETTING_PROMPTS[key]}",
                keyboards.cancel_only("sec:set"))


@router.message(AdminFSM.setting_value)
async def on_setting_value(message: Message, role: str, state: FSMContext) -> None:
    if not roles.has_perm(role, Perm.MANAGE_SETTINGS):
        await state.clear()
        return
    data = await state.get_data()
    await state.clear()
    key = data["key"]
    raw = (message.text or "").strip()
    if key == "download_limit":
        try:
            value = max(0, int(raw))
        except ValueError:
            await message.answer("❌ Not a number.", reply_markup=keyboards.settings_panel())
            return
    else:
        value = "" if raw == "-" else raw
    await settings_store.set(key, value)
    await repo.add_audit(message.from_user.id, "setting_edit", key)
    await message.answer(f"✅ <b>{key}</b> updated.", reply_markup=keyboards.settings_panel())


# ─────────────────────────────── Admin qo'shish ─────────────────────────────

@router.callback_query(F.data == "adm:sys:add")
async def cb_sys_add(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_ADMINS):
        return
    await cq.answer()
    await _edit(cq, f"➕ <b>Add Admin</b>\n{HR}\nChoose a role for the new admin:",
                keyboards.add_admin_roles())


@router.callback_query(F.data.startswith("adm:sys:role:"))
async def cb_sys_role(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_ADMINS):
        return
    new_role = cq.data.rsplit(":", 1)[1]
    if new_role not in (roles.ROLE_ADMIN, roles.ROLE_MODERATOR):
        await cq.answer("Invalid role")
        return
    await state.set_state(AdminFSM.add_admin)
    await state.update_data(role=new_role)
    await cq.answer()
    await _edit(
        cq,
        f"➕ <b>Add {roles.ROLE_LABELS.get(new_role, new_role)}</b>\n{HR}\n"
        f"Send the user's numeric Telegram ID.",
        keyboards.cancel_only("sec:sys"),
    )


@router.message(AdminFSM.add_admin)
async def on_add_admin(message: Message, role: str, state: FSMContext) -> None:
    if not roles.has_perm(role, Perm.MANAGE_ADMINS):
        await state.clear()
        return
    data = await state.get_data()
    await state.clear()
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ Not a valid ID.", reply_markup=keyboards.simple_back())
        return
    uid = int(raw)
    await repo.add_admin(uid, data["role"], message.from_user.id)
    await repo.add_audit(message.from_user.id, "add_admin", str(uid), data["role"])
    await message.answer(
        f"✅ <code>{uid}</code> is now {roles.ROLE_LABELS.get(data['role'], data['role'])}.",
        reply_markup=keyboards.simple_back(),
    )
