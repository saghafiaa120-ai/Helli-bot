"""نقش‌ها و مجوزهای داخلی حلی بات (مستقل از پلتفرم).

در فاز دوم، همه دستورات مدیریتی قبل از اجرا از این‌جا عبور می‌کنند.
"""

from __future__ import annotations

from collections.abc import Collection
from enum import Enum

from core.enums import HelliRole, PlatformRole


class Permission(str, Enum):
    MODERATE_USERS = "moderate_users"
    VIEW_REPORTS = "view_reports"
    MANAGE_SETTINGS = "manage_settings"
    MANAGE_ROLES = "manage_roles"


ROLE_RANK: dict[HelliRole, int] = {
    HelliRole.MODERATOR: 1,
    HelliRole.ADMIN: 2,
    HelliRole.OWNER: 3,
}

ROLE_PERMISSIONS: dict[HelliRole, frozenset[Permission]] = {
    HelliRole.MODERATOR: frozenset({Permission.MODERATE_USERS, Permission.VIEW_REPORTS}),
    HelliRole.ADMIN: frozenset(
        {Permission.MODERATE_USERS, Permission.VIEW_REPORTS, Permission.MANAGE_SETTINGS}
    ),
    HelliRole.OWNER: frozenset(Permission),
}


def derive_role(platform_role: str) -> HelliRole:
    """نقش داخلی را از نقش پلتفرم می‌سازد: سازنده گروه ← owner، مدیر ← admin."""
    if platform_role == PlatformRole.CREATOR.value:
        return HelliRole.OWNER
    return HelliRole.ADMIN


def role_has_permission(role: HelliRole | None, permission: Permission) -> bool:
    """کاربر بدون نقش (None) هیچ مجوزی ندارد."""
    if role is None:
        return False
    return permission in ROLE_PERMISSIONS[role]


def is_global_owner(external_user_id: int, owner_ids: Collection[int]) -> bool:
    """مالک ربات (از OWNER_IDS) در همه گروه‌ها دسترسی کامل دارد."""
    return external_user_id in owner_ids
