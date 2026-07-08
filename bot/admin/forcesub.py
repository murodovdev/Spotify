"""Admin panel: majburiy obuna kanallarini boshqarish.

Kanal qo'shish/o'chirish, yoqish/o'chirish, tartibni o'zgartirish, ekranni
oldindan ko'rish va a'zolik tekshiruvini sinash. Kod o'zgartirmasdan istalgancha
kanal qo'shish mumkin — hammasi `force_subs` jadvalida.

Callback namespace: `adm:fs:*`.
"""

from __future__ import annotations

import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import keyboards as user_kb
from bot.admin import keyboards as adm_kb
from bot.admin import repo, settings_store
from bot.admin.access import AdminFilter, ensure_perm
from bot.admin.roles import Perm
from bot.admin.state import AdminFSM
from bot.db import forcesub_repo
from bot.i18n import Texts
from bot.services import forcesub

log = logging.getLogger(__name__)

router = Router(name="admin_forcesub")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

HR = "━━━━━━━━━━━━━━━━━━━━"


# ─────────────────────────────── Rendering ──────────────────────────────────

def _kb(rows) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, r in enumerate(rows):
        cid = r["chat_id"]
        state = "🟢" if r["enabled"] else "⚪️"
        icon = "👥" if r["kind"] == "group" else "📢"
        kb.row(InlineKeyboardButton(
            text=f"{state} {icon} {r['title'][:28]}", callback_data=f"adm:fs:info:{cid}"
        ))
        kb.row(
            InlineKeyboardButton(text="🔼", callback_data=f"adm:fs:up:{cid}"),
            InlineKeyboardButton(text="🔽", callback_data=f"adm:fs:down:{cid}"),
            InlineKeyboardButton(
                text="⏸ Disable" if r["enabled"] else "▶️ Enable",
                callback_data=f"adm:fs:tog:{cid}",
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"adm:fs:del:{cid}"),
        )
    kb.row(InlineKeyboardButton(text="➕ Add channel / group", callback_data="adm:fs:add"))
    on = bool(settings_store.get("force_sub"))
    kb.row(
        InlineKeyboardButton(
            text="🔴 Turn OFF" if on else "🟢 Turn ON", callback_data="adm:fs:master"
        ),
    )
    kb.row(
        InlineKeyboardButton(text="👁 Preview", callback_data="adm:fs:preview"),
        InlineKeyboardButton(text="🧪 Test", callback_data="adm:fs:test"),
    )
    kb.row(
        InlineKeyboardButton(text="◀️ Back", callback_data="adm:home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="adm:home"),
    )
    return kb.as_markup()


async def render(role: str):
    """dashboard._RENDERERS uchun: (matn, klaviatura)."""
    rows = await forcesub_repo.list_all()
    on = bool(settings_store.get("force_sub"))
    active = sum(1 for r in rows if r["enabled"])

    lines = [
        f"🔒 <b>Force Subscription</b>\n{HR}",
        f"Status: <b>{'🟢 ON' if on else '⚪️ OFF'}</b> · {active}/{len(rows)} active",
        "",
    ]
    broken = forcesub.broken()
    if not rows:
        lines.append("<i>No channels configured yet.</i>")
    else:
        for r in rows:
            handle = f"@{r['username']}" if r["username"] else f"<code>{r['chat_id']}</code>"
            mark = " ❌" if r["chat_id"] in broken else ""
            lines.append(
                f"  {'🟢' if r['enabled'] else '⚪️'} {html.escape(r['title'][:34])} · {handle}{mark}"
            )

    # Majburiy obuna jimgina ishlamay turishi mumkin — buni ko'rsatib qo'yamiz.
    if not on:
        lines.append("\n⚠️ <i>Turned OFF — nobody is being checked.</i>")
    elif active == 0:
        lines.append("\n⚠️ <i>ON, but no active channels — nothing is enforced.</i>")
    elif broken:
        failing = [r for r in rows if r["enabled"] and r["chat_id"] in broken]
        if len(failing) == active:
            lines.append(
                "\n🚨 <b>Every check is failing — nobody is blocked.</b>\n"
                "<i>The bot is probably not an admin in those chats. "
                "Membership errors fail open on purpose, so a broken channel "
                "cannot lock everyone out of the bot. Hit 🧪 Test for details.</i>"
            )
        else:
            lines.append(f"\n⚠️ <i>{len(failing)} chat(s) failing — skipped in checks (❌).</i>")

    return "\n".join(lines), _kb(rows)


async def _refresh(cq: CallbackQuery, role: str) -> None:
    text, kb = await render(role)
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ─────────────────────────────── Actions ────────────────────────────────────

@router.callback_query(F.data == "adm:fs:master")
async def cb_master(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_SETTINGS):
        return
    new = await settings_store.toggle("force_sub")
    await forcesub.reload()
    await repo.add_audit(cq.from_user.id, "force_sub", "master", "on" if new else "off")
    await cq.answer("🟢 Force subscription ON" if new else "⚪️ Force subscription OFF")
    await _refresh(cq, role)


@router.callback_query(F.data.startswith("adm:fs:tog:"))
async def cb_toggle_one(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_SETTINGS):
        return
    chat_id = int(cq.data.rsplit(":", 1)[1])
    row = await forcesub_repo.get(chat_id)
    if not row:
        await cq.answer("Not found")
        return
    await forcesub_repo.set_enabled(chat_id, not row["enabled"])
    await forcesub.reload()
    await cq.answer()
    await _refresh(cq, role)


@router.callback_query(F.data.startswith("adm:fs:del:"))
async def cb_delete(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_SETTINGS):
        return
    chat_id = int(cq.data.rsplit(":", 1)[1])
    await forcesub_repo.remove(chat_id)
    await forcesub.reload()
    await repo.add_audit(cq.from_user.id, "force_sub", str(chat_id), "removed")
    await cq.answer("🗑 Removed")
    await _refresh(cq, role)


@router.callback_query(F.data.startswith("adm:fs:up:") | F.data.startswith("adm:fs:down:"))
async def cb_move(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_SETTINGS):
        return
    parts = cq.data.split(":")
    chat_id = int(parts[3])
    moved = await forcesub_repo.move(chat_id, -1 if parts[2] == "up" else 1)
    if not moved:
        await cq.answer("Already at the edge")
        return
    await forcesub.reload()
    await cq.answer()
    await _refresh(cq, role)


@router.callback_query(F.data.startswith("adm:fs:info:"))
async def cb_info(cq: CallbackQuery, role: str) -> None:
    chat_id = int(cq.data.rsplit(":", 1)[1])
    row = await forcesub_repo.get(chat_id)
    if not row:
        await cq.answer("Not found")
        return
    link = forcesub.chat_url(row) or "—"
    await cq.answer(
        f"{row['title']}\nid: {row['chat_id']}\ntype: {row['kind']}\n{link}",
        show_alert=True,
    )


@router.callback_query(F.data == "adm:fs:preview")
async def cb_preview(cq: CallbackQuery, role: str, t: Texts) -> None:
    chats = await forcesub_repo.list_enabled()
    if not chats:
        await cq.answer("No active channels", show_alert=True)
        return
    await cq.answer()
    await cq.message.answer(t.FS_TITLE, reply_markup=user_kb.force_sub(chats, t))


@router.callback_query(F.data == "adm:fs:test")
async def cb_test(cq: CallbackQuery, role: str, bot: Bot) -> None:
    """Har bir kanal uchun tekshiruvni sinaydi va aniq sababni ko'rsatadi.

    `forcesub._is_member` konfiguratsiya xatosida fail-open bo'ladi; bu yerda
    esa admin aynan nima buzilganini ko'rishi kerak, shuning uchun xatoni
    to'g'ridan-to'g'ri ushlaymiz.
    """
    rows = await forcesub_repo.list_all()
    if not rows:
        await cq.answer("Nothing to test", show_alert=True)
        return

    lines = [f"🧪 <b>Membership test</b> (you)\n{HR}"]
    for r in rows:
        try:
            member = await bot.get_chat_member(r["chat_id"], cq.from_user.id)
            lines.append(f"  ✅ {html.escape(r['title'][:30])} · <code>{member.status}</code>")
        except TelegramAPIError as e:
            lines.append(f"  ❌ {html.escape(r['title'][:30])} · {html.escape(str(e)[:60])}")

    lines.append("\n<i>❌ usually means the bot is not an admin in that chat.</i>")
    await cq.answer()
    await cq.message.answer("\n".join(lines), reply_markup=adm_kb.simple_back())


# ─────────────────────────── Add channel (FSM) ──────────────────────────────

@router.callback_query(F.data == "adm:fs:add")
async def cb_add(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.MANAGE_SETTINGS):
        return
    await state.set_state(AdminFSM.fs_add)
    await cq.answer()
    await cq.message.edit_text(
        f"➕ <b>Add required chat</b>\n{HR}\n"
        "Send <b>@username</b>, a numeric chat id (<code>-100…</code>), "
        "or simply <b>forward any message</b> from the channel.\n\n"
        "<i>The bot must already be an administrator there.</i>",
        reply_markup=adm_kb.cancel_only("sec:fs"),
    )


def _extract_target(message: Message) -> str | int | None:
    """@username, -100… id yoki forward qilingan xabardan chat id."""
    fwd = getattr(message, "forward_from_chat", None)
    if fwd is not None:
        return fwd.id
    raw = (message.text or "").strip()
    if not raw:
        return None
    if raw.startswith("@") and len(raw) > 1:
        return raw
    if raw.startswith("https://t.me/"):
        tail = raw.rsplit("/", 1)[-1]
        return f"@{tail}" if tail and not tail.startswith("+") else None
    try:
        return int(raw)
    except ValueError:
        return None


@router.message(AdminFSM.fs_add)
async def on_add(message: Message, role: str, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    target = _extract_target(message)
    if target is None:
        await message.answer(
            "❌ Couldn't read that. Send @username, a -100… id, or forward a message.",
            reply_markup=adm_kb.simple_back(),
        )
        return

    try:
        chat = await bot.get_chat(target)
    except TelegramAPIError as e:
        await message.answer(
            f"❌ Chat not reachable.\n<code>{html.escape(str(e)[:120])}</code>",
            reply_markup=adm_kb.simple_back(),
        )
        return

    # Bot admin bo'lmasa getChatMember ishonchsiz — obuna tekshiruvi jim buziladi.
    try:
        me = await bot.get_chat_member(chat.id, bot.id)
        if me.status not in ("administrator", "creator"):
            await message.answer(
                f"❌ The bot is <b>not an admin</b> in {html.escape(chat.title or str(chat.id))}.\n"
                "Membership checks would silently fail. Promote it first.",
                reply_markup=adm_kb.simple_back(),
            )
            return
    except TelegramAPIError as e:
        await message.answer(
            f"❌ Can't verify the bot's admin rights.\n<code>{html.escape(str(e)[:120])}</code>",
            reply_markup=adm_kb.simple_back(),
        )
        return

    kind = "channel" if chat.type == "channel" else "group"
    invite = chat.invite_link
    if not chat.username and not invite:
        # Maxfiy chat: havolasiz tugma yasab bo'lmaydi.
        try:
            invite = (await bot.create_chat_invite_link(chat.id)).invite_link
        except TelegramAPIError:
            await message.answer(
                "❌ Private chat with no invite link, and the bot lacks the "
                "<i>invite users</i> right to create one.",
                reply_markup=adm_kb.simple_back(),
            )
            return

    await forcesub_repo.add(chat.id, chat.username, chat.title or str(chat.id), kind, invite)
    await forcesub.reload()
    await repo.add_audit(message.from_user.id, "force_sub", str(chat.id), "added")

    text, kb = await render(role)
    await message.answer(f"✅ Added <b>{html.escape(chat.title or '')}</b>.\n\n{text}", reply_markup=kb)
