"""قرارداد مشترک پلتفرم‌ها.

سرویس‌های اصلی هیچ‌گاه مستقیم با API تلگرام (یا هر پلتفرم دیگر) صحبت نمی‌کنند؛
هر پلتفرم این قرارداد را پیاده‌سازی می‌کند. در فازهای بعد، عملیات اجرایی
(ban، mute، حذف پیام) به همین رابط اضافه می‌شود.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from domain.dto import AdminInfo, BotStatus, ChatRef


class PlatformError(Exception):
    """خطای ارتباط با API پلتفرم (مستقل از نوع پلتفرم).

    kind دسته خطا را برای نمایش پیام مناسب به کاربر مشخص می‌کند:
    no_rights | target_is_admin | not_found | not_supergroup | rate_limited | other
    """

    def __init__(self, message: str, kind: str = "other") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class Capabilities:
    """قابلیت‌هایی که پلتفرم پشتیبانی می‌کند؛ منطق مشترک بر اساس آن تصمیم می‌گیرد."""

    can_restrict_members: bool
    can_delete_messages: bool
    supports_buttons: bool


class PlatformAdapter(ABC):
    platform: str
    capabilities: Capabilities

    @property
    @abstractmethod
    def bot_user_id(self) -> int:
        """شناسه خود ربات در پلتفرم."""

    @abstractmethod
    async def get_admins(self, chat: ChatRef) -> list[AdminInfo]:
        """فهرست مدیران واقعی گروه طبق پلتفرم."""

    @abstractmethod
    async def get_bot_status(self, chat: ChatRef) -> BotStatus:
        """وضعیت و دسترسی‌های خود ربات در گروه."""

    @abstractmethod
    async def get_member_count(self, chat: ChatRef) -> int:
        """تعداد اعضای گروه."""

    @abstractmethod
    async def send_text(self, chat: ChatRef, text: str) -> None:
        """ارسال یک پیام متنی به گروه."""

    @abstractmethod
    async def ban_member(self, chat: ChatRef, user_id: int, until: datetime | None) -> None:
        """مسدود کردن کاربر؛ until زمان UTC (بدون tzinfo) پایان مسدودی یا None برای دائمی."""

    @abstractmethod
    async def unban_member(self, chat: ChatRef, user_id: int) -> bool:
        """رفع مسدودی. اگر کاربر در پلتفرم مسدود بوده True، وگرنه False."""

    @abstractmethod
    async def mute_member(self, chat: ChatRef, user_id: int, until: datetime | None) -> None:
        """بی‌صدا کردن کاربر (همه انواع ارسال پیام)."""

    @abstractmethod
    async def unmute_member(self, chat: ChatRef, user_id: int) -> bool:
        """رفع سکوت. اگر کاربر در پلتفرم بی‌صدا بوده True، وگرنه False."""

    @abstractmethod
    async def kick_member(self, chat: ChatRef, user_id: int) -> None:
        """اخراج کاربر بدون مسدود ماندن (می‌تواند دوباره عضو شود)."""
