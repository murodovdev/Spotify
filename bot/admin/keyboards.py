"""Admin panel inline klaviaturalari.

Callback namespace: barcha admin callbacklari `adm:` bilan boshlanadi.
Har sahifada izchil navigatsiya: 🏠 Home / ◀️ Back.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.admin import roles, settings_store
from bot.admin.roles import Perm

# (label, section_key, ruxsat) — dashboard bo'limlari
SECTIONS = [
    ("👥 Users",       "users",   Perm.MANAGE_USERS),
    ("📊 Analytics",   "an",      Perm.VIEW),
    ("📢 Broadcast",   "bc",      Perm.BROADCAST),
    ("🎵 Music",       "music",   Perm.MANAGE_MUSIC),
    ("⚙️ Settings",    "set",     Perm.MANAGE_SETTINGS),
    ("🌐 Language",    "lang",    Perm.VIEW),
    ("🚫 Moderation",  "mod",     Perm.MODERATE),
    ("💾 Database",    "db",      Perm.MANAGE_DB),
    ("📈 Performance", "perf",    Perm.VIEW),
    ("📂 Queue",       "queue",   Perm.MANAGE_QUEUE),
    ("🔧 System",      "sys",     Perm.MANAGE_ADMINS),
    ("📜 Logs",        "logs",    Perm.VIEW_LOGS),
]


def _nav(back: str = "home", *, home: bool = True) -> list[InlineKeyboardButton]:
    row = [InlineKeyboardButton(text="◀️ Back", callback_data=f"adm:{back}")]
    if home:
        row.append(InlineKeyboardButton(text="🏠 Home", callback_data="adm:home"))
    return row


def dashboard(role: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    visible = [(lbl, key) for lbl, key, perm in SECTIONS if roles.has_perm(role, perm)]
    for i in range(0, len(visible), 2):
        kb.row(*[
            InlineKeyboardButton(text=lbl, callback_data=f"adm:sec:{key}")
            for lbl, key in visible[i:i + 2]
        ])
    kb.row(InlineKeyboardButton(text="🔄 Refresh", callback_data="adm:home"))
    return kb.as_markup()


def section_back(section: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_nav()])


# ─────────────────────────────── Users ──────────────────────────────────────

def users_home() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔍 Search user", callback_data="adm:u:search"))
    kb.row(*_nav())
    return kb.as_markup()


def users_results(rows) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in rows:
        uname = f"@{r['username']}" if r["username"] else (r["first_name"] or str(r["id"]))
        kb.button(text=f"👤 {uname}"[:60], callback_data=f"adm:u:v:{r['id']}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="🔍 New search", callback_data="adm:u:search"))
    kb.row(*_nav("sec:users"))
    return kb.as_markup()


def user_profile(user_id: int, blocked: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✉️ Message", callback_data=f"adm:u:dm:{user_id}"),
        InlineKeyboardButton(text="♻️ Reset", callback_data=f"adm:u:rstc:{user_id}"),
    )
    if blocked:
        kb.row(InlineKeyboardButton(text="✅ Unban", callback_data=f"adm:mod:unban:{user_id}"))
    else:
        kb.row(
            InlineKeyboardButton(text="🚫 Ban", callback_data=f"adm:u:ban:{user_id}"),
            InlineKeyboardButton(text="⏳ Suspend 24h", callback_data=f"adm:u:susp:{user_id}"),
        )
    kb.row(*_nav("sec:users"))
    return kb.as_markup()


def confirm(action: str, arg: str, back: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Confirm", callback_data=f"adm:{action}:{arg}"),
            InlineKeyboardButton(text="✕ Cancel", callback_data=f"adm:{back}"),
        ]
    ])


def cancel_only(back: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✕ Cancel", callback_data=f"adm:{back}")]
    ])


def confirm_action(confirm_cb: str, back: str, label: str = "✅ Confirm") -> InlineKeyboardMarkup:
    """Destruktiv amal uchun tasdiqlash: [label → confirm_cb] [✕ Cancel → adm:{back}]."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label, callback_data=confirm_cb),
        InlineKeyboardButton(text="✕ Cancel", callback_data=f"adm:{back}"),
    ]])


# ────────────────────────────── Broadcast ───────────────────────────────────

def broadcast_home() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✍️ New broadcast", callback_data="adm:bc:new"))
    kb.row(*_nav())
    return kb.as_markup()


def broadcast_preview() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🚀 Send now", callback_data="adm:bc:send"),
        InlineKeyboardButton(text="✕ Cancel", callback_data="adm:sec:bc"),
    )
    return kb.as_markup()


def broadcast_running(bid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Stop broadcast", callback_data=f"adm:bc:stop:{bid}")]
    ])


# ────────────────────────────── Settings ────────────────────────────────────

def settings_panel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    labels = {
        "maintenance": "🛠 Maintenance mode",
        "feature_search": "🔍 Search",
        "feature_recognize": "🎧 Recognition",
        "feature_video": "🎬 Video download",
        "feature_similar": "🎵 Similar songs",
        "feature_effects": "🎚 Audio effects",
    }
    for key, label in labels.items():
        on = bool(settings_store.get(key))
        mark = "🟢" if on else "🔴"
        kb.row(InlineKeyboardButton(text=f"{mark} {label}", callback_data=f"adm:set:t:{key}"))
    kb.row(
        InlineKeyboardButton(text="✏️ Welcome msg", callback_data="adm:set:e:welcome_override"),
        InlineKeyboardButton(text="📣 Announcement", callback_data="adm:set:e:announcement"),
    )
    kb.row(InlineKeyboardButton(text="⬇️ Download limit", callback_data="adm:set:e:download_limit"))
    kb.row(*_nav())
    return kb.as_markup()


# ─────────────────────────────── Moderation ─────────────────────────────────

def moderation_home(rows, offset: int, has_more: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in rows:
        kind = "🚫" if r["kind"] == "ban" else "⏳"
        kb.button(text=f"{kind} {r['user_id']}", callback_data=f"adm:u:v:{r['user_id']}")
    kb.adjust(1)
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"adm:mod:p:{offset - 8}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"adm:mod:p:{offset + 8}"))
    if nav:
        kb.row(*nav)
    kb.row(*_nav())
    return kb.as_markup()


# ─────────────────────────────── Database ───────────────────────────────────

def database_panel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🧹 Run maintenance", callback_data="adm:db:maint"))
    kb.row(InlineKeyboardButton(text="🩺 Integrity check", callback_data="adm:db:check"))
    kb.row(*_nav())
    return kb.as_markup()


# ─────────────────────────────── Music ──────────────────────────────────────

def music_panel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🗑 Clear metadata cache", callback_data="adm:music:clearc"))
    kb.row(*_nav())
    return kb.as_markup()


# ─────────────────────────────── Logs ───────────────────────────────────────

def logs_panel(active: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    tabs = [("Errors", "ERROR"), ("Warnings", "WARNING"), ("Audit", "AUDIT")]
    kb.row(*[
        InlineKeyboardButton(
            text=("• " + name + " •") if key == active else name,
            callback_data=f"adm:log:{key}",
        )
        for name, key in tabs
    ])
    kb.row(*_nav())
    return kb.as_markup()


# ─────────────────────────────── System ─────────────────────────────────────

def system_panel(admins_rows, can_manage: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_manage:
        for r in admins_rows:
            kb.button(
                text=f"{roles.ROLE_LABELS.get(r['role'], r['role'])} · {r['user_id']}",
                callback_data=f"adm:sys:rmc:{r['user_id']}",
            )
        kb.adjust(1)
        kb.row(InlineKeyboardButton(text="➕ Add admin", callback_data="adm:sys:add"))
    kb.row(*_nav())
    return kb.as_markup()


def add_admin_roles() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🛡 Admin", callback_data="adm:sys:role:admin"),
        InlineKeyboardButton(text="🧹 Moderator", callback_data="adm:sys:role:moderator"),
    )
    kb.row(InlineKeyboardButton(text="✕ Cancel", callback_data="adm:sec:sys"))
    return kb.as_markup()


# ─────────────────────── Generic section reload ─────────────────────────────

def simple_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_nav()])
