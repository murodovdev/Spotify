"""Professional broadcast moduli.

Har qanday kontent turini (matn/rasm/video/audio/ovoz/hujjat/so'rovnoma)
`copy_message` orqali qayta yuboradi — preview, progress, yetkazib berish
statistikasi va to'xtatish bilan.
"""

from __future__ import annotations

import asyncio
import html
import logging
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.admin import keyboards, repo, roles
from bot.admin.access import AdminFilter, ensure_perm
from bot.admin.roles import Perm
from bot.admin.state import AdminFSM

log = logging.getLogger(__name__)

router = Router(name="admin_broadcast")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

HR = "━━━━━━━━━━━━━━━━━━━━"

# Ishlab turgan broadcastlar: bid → {"cancel": bool}
_running: dict[int, dict] = {}

_THROTTLE = 0.05          # ~20 xabar/s (Telegram limitидан past)
_PROGRESS_EVERY = 2.5     # progressни yangilash oralig'i (s)


@router.callback_query(F.data == "adm:bc:new")
async def cb_new(cq: CallbackQuery, role: str, state: FSMContext) -> None:
    if not await ensure_perm(cq, role, Perm.BROADCAST):
        return
    await state.set_state(AdminFSM.broadcast_compose)
    await cq.answer()
    await cq.message.edit_text(
        f"✍️ <b>Compose Broadcast</b>\n{HR}\n"
        f"Send the message to broadcast — text, photo, video, audio, voice, "
        f"document, or poll. You'll preview it before sending.",
        reply_markup=keyboards.cancel_only("sec:bc"),
    )


@router.message(AdminFSM.broadcast_compose)
async def on_compose(message: Message, role: str, state: FSMContext, bot: Bot) -> None:
    if not roles.has_perm(role, Perm.BROADCAST):
        await state.clear()
        return
    await state.update_data(
        src_chat=message.chat.id,
        src_msg=message.message_id,
        kind=message.content_type,
    )
    await state.set_state(None)  # kompozitsiya tugadi, preview kutilyapti
    # Preview: kontentни o'ziга qaytarib nusxalaymiz
    try:
        await bot.copy_message(message.chat.id, message.chat.id, message.message_id)
    except Exception:
        pass
    await message.answer(
        f"👀 <b>Preview above</b>\n{HR}\n"
        f"Type: <b>{message.content_type}</b>\nReady to send to all users?",
        reply_markup=keyboards.broadcast_preview(),
    )


@router.callback_query(F.data == "adm:bc:send")
async def cb_send(cq: CallbackQuery, role: str, state: FSMContext, bot: Bot) -> None:
    if not await ensure_perm(cq, role, Perm.BROADCAST):
        return
    data = await state.get_data()
    await state.clear()
    src_chat = data.get("src_chat")
    src_msg = data.get("src_msg")
    if not src_chat or not src_msg:
        await cq.answer("Nothing to send — compose again.", show_alert=True)
        return
    await cq.answer("🚀 Broadcast started")
    total = max(0, await repo.count_users() - await repo.count_bans())
    bid = await repo.create_broadcast(cq.from_user.id, data.get("kind", "text"), total)
    await repo.add_audit(cq.from_user.id, "broadcast_start", str(bid), f"{total} users")
    _running[bid] = {"cancel": False}
    status = await cq.message.edit_text(
        f"🚀 <b>Broadcasting #{bid}</b>\n{HR}\nStarting…",
        reply_markup=keyboards.broadcast_running(bid),
    )
    asyncio.create_task(_run(bot, bid, src_chat, src_msg, total, status))


@router.callback_query(F.data.startswith("adm:bc:stop:"))
async def cb_stop(cq: CallbackQuery, role: str) -> None:
    if not await ensure_perm(cq, role, Perm.BROADCAST):
        return
    bid = int(cq.data.rsplit(":", 1)[1])
    st = _running.get(bid)
    if st:
        st["cancel"] = True
        await cq.answer("🛑 Stopping…")
    else:
        await cq.answer("Not running")


async def _run(bot: Bot, bid: int, src_chat: int, src_msg: int, total: int, status: Message) -> None:
    sent = failed = done = 0
    last_edit = 0.0
    state = _running[bid]
    try:
        async for uid in repo.iter_active_user_ids():
            if state["cancel"]:
                break
            done += 1
            try:
                await bot.copy_message(uid, src_chat, src_msg)
                sent += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 0.5)
                try:
                    await bot.copy_message(uid, src_chat, src_msg)
                    sent += 1
                except Exception:
                    failed += 1
            except TelegramForbiddenError:
                failed += 1  # foydalanuvchi botни bloklagan
            except Exception:
                failed += 1
            now = time.monotonic()
            if now - last_edit > _PROGRESS_EVERY:
                pct = round(done * 100 / total) if total else 100
                await _safe_edit(
                    status,
                    f"🚀 <b>Broadcasting #{bid}</b>\n{HR}\n"
                    f"Progress: <b>{done}/{total}</b> ({pct}%)\n"
                    f"✅ Sent: <b>{sent}</b>   ❌ Failed: <b>{failed}</b>",
                    keyboards.broadcast_running(bid),
                )
                last_edit = now
                await repo.update_broadcast(bid, sent=sent, failed=failed)
            await asyncio.sleep(_THROTTLE)
    except Exception:
        log.exception("Broadcast #%s crashed", bid)
    finally:
        cancelled = state["cancel"]
        _running.pop(bid, None)
        await repo.update_broadcast(
            bid, status="cancelled" if cancelled else "done",
            sent=sent, failed=failed, finished_at=time.time(),
        )
        head = "🛑 <b>Broadcast stopped</b>" if cancelled else "✅ <b>Broadcast complete</b>"
        await _safe_edit(
            status,
            f"{head} #{bid}\n{HR}\n"
            f"👥 Reached: <b>{done}/{total}</b>\n"
            f"✅ Delivered: <b>{sent}</b>\n"
            f"❌ Failed: <b>{failed}</b>",
            keyboards.simple_back(),
        )


async def _safe_edit(msg: Message, text: str, kb) -> None:
    try:
        await msg.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass
