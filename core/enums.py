"""مقادیر ثابت مشترک. مقدار (`.value`) رشته‌ای است که در دیتابیس ذخیره می‌شود."""

from __future__ import annotations

from enum import Enum


class Platform(str, Enum):
    TELEGRAM = "telegram"
    BALE = "bale"
    DISCORD = "discord"


class MemberStatus(str, Enum):
    MEMBER = "member"
    LEFT = "left"
    BANNED = "banned"


class PlatformRole(str, Enum):
    """نقش اعلام‌شده توسط خود پلتفرم."""

    CREATOR = "creator"
    ADMIN = "admin"


class HelliRole(str, Enum):
    """نقش داخلی در حلی بات."""

    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"


class AuditAction(str, Enum):
    GROUP_REGISTERED = "group.registered"
    GROUP_BOT_REMOVED = "group.bot_removed"
    GROUP_MIGRATED = "group.migrated"
    ADMINS_SYNCED = "group.admins_synced"


class RestrictionType(str, Enum):
    BAN = "ban"
    MUTE = "mute"


class ModerationActionType(str, Enum):
    BAN = "ban"
    UNBAN = "unban"
    MUTE = "mute"
    UNMUTE = "unmute"
    KICK = "kick"
    WARN = "warn"
    UNWARN = "unwarn"
    # پایان خودکار مدت مسدودی موقت (بدون دخالت مدیر)
    AUTO_UNBAN = "auto_unban"


class EndReason(str, Enum):
    """دلیل پایان یافتن یک محدودیت یا اخطار."""

    MANUAL = "manual"      # مدیر با دستور برداشت
    REPLACED = "replaced"  # محدودیت جدید جایگزین شد
    KICKED = "kicked"      # کاربر اخراج شد
    EXTERNAL = "external"  # خارج از ربات (مثلاً از منوی تلگرام) برداشته شد
    EXPIRED = "expired"    # مدت آن تمام شد
    LIMIT = "limit"        # اخطارها به سقف رسیدند و تبدیل به سکوت شدند
