"""تبدیل نوع‌های تلگرام (aiogram) به ساختارهای مستقل از پلتفرم.

توابع این ماژول فقط به صفت‌های اشیاء تکیه دارند (duck typing) و aiogram را import
نمی‌کنند؛ بنابراین بدون نصب aiogram هم قابل تست‌اند.
"""

from __future__ import annotations

from typing import Any

from core.enums import MemberStatus, Platform, PlatformRole
from domain.dto import AdminInfo, BotStatus, ChatRef, UserRef

PLATFORM = Platform.TELEGRAM.value
GROUP_CHAT_TYPES = frozenset({"group", "supergroup"})

# دسترسی‌های مدیر که از تلگرام ذخیره می‌شوند.
ADMIN_PERMISSION_FIELDS: tuple[str, ...] = (
    "can_manage_chat",
    "can_delete_messages",
    "can_restrict_members",
    "can_promote_members",
    "can_change_info",
    "can_invite_users",
    "can_pin_messages",
    "can_manage_topics",
    "can_manage_video_chats",
)


def enum_value(value: Any) -> str:
    """مقدار رشته‌ای یک Enum (یا خود رشته)."""
    return str(getattr(value, "value", value))


def status_value(member: Any) -> str:
    return enum_value(member.status)


def user_ref_from(user: Any) -> UserRef:
    return UserRef(
        platform=PLATFORM,
        external_id=int(user.id),
        username=getattr(user, "username", None),
        first_name=getattr(user, "first_name", None),
        last_name=getattr(user, "last_name", None),
        language_code=getattr(user, "language_code", None),
        is_bot=bool(getattr(user, "is_bot", False)),
    )


def chat_ref_from(chat: Any) -> ChatRef:
    return ChatRef(
        platform=PLATFORM,
        external_id=int(chat.id),
        title=getattr(chat, "title", None),
        username=getattr(chat, "username", None),
        kind=enum_value(chat.type),
    )


def chat_ref_from_group(group: Any) -> ChatRef:
    """ChatRef از رکورد دیتابیس گروه (وقتی پیام تلگرام در دسترس نیست)."""
    return ChatRef(
        platform=group.platform,
        external_id=group.external_id,
        title=group.title,
        username=group.username,
        kind="supergroup",
    )


def admin_info_from(member: Any) -> AdminInfo | None:
    """اطلاعات مدیر از ChatMemberOwner/ChatMemberAdministrator؛ برای غیرمدیر None."""
    status = status_value(member)
    if status == "creator":
        return AdminInfo(
            user=user_ref_from(member.user),
            platform_role=PlatformRole.CREATOR.value,
            permissions={field: True for field in ADMIN_PERMISSION_FIELDS},
        )
    if status == "administrator":
        return AdminInfo(
            user=user_ref_from(member.user),
            platform_role=PlatformRole.ADMIN.value,
            permissions={field: bool(getattr(member, field, False)) for field in ADMIN_PERMISSION_FIELDS},
        )
    return None


def bot_status_from(member: Any) -> BotStatus:
    """وضعیت ربات از روی ChatMember خودِ ربات."""
    status = status_value(member)
    if status == "creator":
        return BotStatus(is_admin=True, can_delete_messages=True, can_restrict_members=True)
    if status == "administrator":
        return BotStatus(
            is_admin=True,
            can_delete_messages=bool(getattr(member, "can_delete_messages", False)),
            can_restrict_members=bool(getattr(member, "can_restrict_members", False)),
        )
    return BotStatus()


def member_status_from(member: Any) -> str:
    """تبدیل وضعیت عضویت تلگرام به مقادیر داخلی (member | left | banned)."""
    status = status_value(member)
    if status in ("creator", "administrator", "member"):
        return MemberStatus.MEMBER.value
    if status == "restricted":
        is_member = getattr(member, "is_member", True)
        return MemberStatus.MEMBER.value if is_member else MemberStatus.LEFT.value
    if status == "kicked":
        return MemberStatus.BANNED.value
    return MemberStatus.LEFT.value
