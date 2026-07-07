"""Admin rollari va fine-grained ruxsatlar tizimi."""

from __future__ import annotations

from enum import Enum

# Rollar (kuch tartibida)
ROLE_SUPER = "super"
ROLE_ADMIN = "admin"
ROLE_MODERATOR = "moderator"

ROLE_LABELS = {
    ROLE_SUPER: "👑 Super Admin",
    ROLE_ADMIN: "🛡 Admin",
    ROLE_MODERATOR: "🧹 Moderator",
}


class Perm(str, Enum):
    VIEW = "view"                 # dashboard, statistika, loglar ko'rish
    MANAGE_USERS = "manage_users"   # profil, reset, xabar yuborish
    MODERATE = "moderate"         # ban / unban / suspend
    BROADCAST = "broadcast"       # ommaviy xabar
    MANAGE_SETTINGS = "settings"  # bot konfiguratsiyasi
    MANAGE_MUSIC = "music"        # kesh, indeks, music management
    MANAGE_QUEUE = "queue"        # navbat / joblar
    MANAGE_DB = "db"              # ma'lumotlar bazasi maintenance
    MANAGE_ADMINS = "admins"      # adminlarni qo'shish/olib tashlash
    VIEW_LOGS = "logs"            # loglar va audit


# Har bir rol egallagan ruxsatlar to'plami.
_ALL = set(Perm)
_ADMIN = {
    Perm.VIEW, Perm.MANAGE_USERS, Perm.MODERATE, Perm.BROADCAST,
    Perm.MANAGE_SETTINGS, Perm.MANAGE_MUSIC, Perm.MANAGE_QUEUE,
    Perm.MANAGE_DB, Perm.VIEW_LOGS,
}
_MODERATOR = {Perm.VIEW, Perm.MANAGE_USERS, Perm.MODERATE, Perm.VIEW_LOGS}

ROLE_PERMS: dict[str, set[Perm]] = {
    ROLE_SUPER: _ALL,
    ROLE_ADMIN: _ADMIN,
    ROLE_MODERATOR: _MODERATOR,
}


def perms_for(role: str) -> set[Perm]:
    return ROLE_PERMS.get(role, set())


def has_perm(role: str, perm: Perm) -> bool:
    return perm in perms_for(role)
