"""وارد کردن همه مدل‌ها تا در `Base.metadata` ثبت شوند (برای Alembic و تست‌ها)."""

from database.models.audit_log import AuditLog
from database.models.daily_message_count import DailyMessageCount
from database.models.group import Group
from database.models.group_admin import GroupAdmin
from database.models.group_member import GroupMember
from database.models.group_settings import GroupSettings
from database.models.moderation_action import ModerationAction
from database.models.restriction import Restriction
from database.models.user import User
from database.models.warning import Warning

__all__ = [
    "AuditLog",
    "DailyMessageCount",
    "Group",
    "GroupAdmin",
    "GroupMember",
    "GroupSettings",
    "ModerationAction",
    "Restriction",
    "User",
    "Warning",
]
