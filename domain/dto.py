"""ساختارهای داده مستقل از پلتفرم.

منطق اصلی حلی بات فقط با این ساختارها کار می‌کند؛ تبدیل از/به نوع‌های هر پلتفرم
(مثلاً aiogram) در لایه `platforms/<name>/` انجام می‌شود.
مقدار `platform` همیشه رشته ساده است (`Platform.X.value`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# دسترسی‌هایی که ربات برای عملکرد کامل در گروه لازم دارد (حداقل مجوز لازم).
REQUIRED_BOT_PERMISSIONS: tuple[str, ...] = ("can_delete_messages", "can_restrict_members")


@dataclass(frozen=True, slots=True)
class UserRef:
    platform: str
    external_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    is_bot: bool = False


@dataclass(frozen=True, slots=True)
class ChatRef:
    platform: str
    external_id: int
    title: str | None = None
    username: str | None = None
    kind: str = "group"


@dataclass(frozen=True, slots=True)
class AdminInfo:
    user: UserRef
    platform_role: str  # PlatformRole.value
    permissions: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BotStatus:
    """وضعیت و دسترسی‌های خود ربات در یک گروه."""

    is_admin: bool = False
    can_delete_messages: bool = False
    can_restrict_members: bool = False

    @property
    def missing_permissions(self) -> tuple[str, ...]:
        """کلیدهای دسترسی‌های ناقص؛ اگر ربات مدیر نباشد فقط `is_admin`."""
        if not self.is_admin:
            return ("is_admin",)
        return tuple(p for p in REQUIRED_BOT_PERMISSIONS if not getattr(self, p))


@dataclass(frozen=True, slots=True)
class ModerationSettings:
    """تنظیمات مدیریتی هر گروه (از ستون‌های group_settings خوانده می‌شود).

    warn_limit: با رسیدن اخطارهای فعال به این عدد، کاربر موقتاً بی‌صدا می‌شود (۰ = خاموش).
    """

    confirm_sensitive_actions: bool = True
    warn_limit: int = 3
    warn_mute_seconds: int = 86400
