from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AuditAction
from core.timeutils import utcnow
from database.models import Group, GroupSettings
from database.repositories.groups import GroupRepository
from domain.dto import BotStatus, ChatRef, ModerationSettings
from services.audit_service import AuditService

logger = logging.getLogger(__name__)

SETTING_DAILY_REPORT = "daily_report"
SETTING_LAST_DAILY_REPORT = "last_daily_report"


def _as_int(value: object, default: int, low: int, high: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default


class GroupService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._groups = GroupRepository(session)
        self._audit = AuditService(session)

    async def register(
        self,
        chat: ChatRef,
        status: BotStatus | None = None,
        *,
        actor_user_id: int | None = None,
        source: str = "my_chat_member",
    ) -> tuple[Group, bool]:
        """گروه را ثبت (یا دوباره فعال) می‌کند.

        خروجی: (گروه، joined). `joined` یعنی گروه تازه ساخته شده یا ربات پس از
        خروج دوباره به آن اضافه شده است.
        """
        group, created = await self._groups.get_or_create(chat)
        reactivated = not created and not group.is_active
        self._groups.apply_chat_info(group, chat)

        group.is_active = True
        group.left_at = None
        if status is not None:
            group.bot_is_admin = status.is_admin
        if reactivated:
            group.added_at = utcnow()

        joined = created or reactivated
        if joined:
            await self._audit.log(
                AuditAction.GROUP_REGISTERED,
                group_id=group.id,
                actor_user_id=actor_user_id,
                details={"source": source, "reactivated": reactivated, "chat_kind": chat.kind},
            )
        return group, joined

    async def ensure(self, chat: ChatRef) -> tuple[Group, bool]:
        """اطمینان از وجود گروه هنگام دیدن فعالیت در آن (گروه‌های قبل از نصب ربات)."""
        return await self.register(chat, None, source="activity")

    async def mark_bot_removed(
        self, chat: ChatRef, *, actor_user_id: int | None = None
    ) -> Group | None:
        """ثبت خروج ربات از گروه. اگر گروه ثبت نشده یا قبلاً غیرفعال بوده، کاری نمی‌کند."""
        group = await self._groups.get(chat.platform, chat.external_id)
        if group is None or not group.is_active:
            return None
        group.is_active = False
        group.bot_is_admin = False
        group.left_at = utcnow()
        await self._audit.log(
            AuditAction.GROUP_BOT_REMOVED, group_id=group.id, actor_user_id=actor_user_id
        )
        return group

    async def set_bot_status(self, group: Group, status: BotStatus) -> None:
        group.bot_is_admin = status.is_admin

    async def active_groups(self, platform: str | None = None) -> list[Group]:
        """گروه‌هایی که ربات هنوز عضو آن‌هاست."""
        return await self._groups.list_active(platform)

    async def get_by_id(self, group_id: int) -> Group | None:
        return await self._groups.get_by_id(group_id)

    async def get_by_external(self, platform: str, external_id: int) -> Group | None:
        return await self._groups.get(platform, external_id)

    async def groups_by_ids(self, group_ids: list[int]) -> list[Group]:
        return await self._groups.list_by_ids(group_ids)

    async def set_member_count(self, group: Group, count: int) -> None:
        group.member_count = count

    async def migrate(self, platform: str, old_external_id: int, new_external_id: int) -> Group | None:
        """انتقال گروه عادی به سوپرگروه (تغییر شناسه). تاریخچه گروه حفظ می‌شود.

        اگر شناسه جدید از قبل ثبت شده باشد، گروه قدیمی فقط غیرفعال می‌شود تا
        رکوردها ادغام نشوند.
        """
        old = await self._groups.get(platform, old_external_id)
        if old is None:
            return None

        existing_new = await self._groups.get(platform, new_external_id)
        if existing_new is not None:
            logger.warning(
                "Group %s migrated to %s which is already registered; deactivating old record",
                old_external_id,
                new_external_id,
            )
            old.is_active = False
            old.left_at = utcnow()
            return old

        old.external_id = new_external_id
        await self._audit.log(
            AuditAction.GROUP_MIGRATED,
            group_id=old.id,
            details={"old_external_id": old_external_id, "new_external_id": new_external_id},
        )
        return old

    async def moderation_settings(self, group_id: int) -> ModerationSettings:
        """تنظیمات مدیریتی گروه؛ مقدارهای نامعتبر یا خالی با پیش‌فرض جایگزین می‌شوند."""
        row = await self._session.get(GroupSettings, group_id)
        if row is None:
            return ModerationSettings()
        raw = row.settings or {}
        return ModerationSettings(
            confirm_sensitive_actions=bool(row.confirm_sensitive_actions),
            warn_limit=_as_int(raw.get("warn_limit"), 3, 0, 50),
            warn_mute_seconds=_as_int(raw.get("warn_mute_seconds"), 86400, 30, 366 * 86400),
        )

    async def daily_report_enabled(self, group_id: int) -> bool:
        row = await self._session.get(GroupSettings, group_id)
        if row is None:
            return True
        return bool((row.settings or {}).get(SETTING_DAILY_REPORT, True))

    async def last_daily_report(self, group_id: int) -> str | None:
        """تاریخ (ISO) آخرین گزارش شبانه ارسال‌شده؛ برای جلوگیری از ارسال دوباره."""
        row = await self._session.get(GroupSettings, group_id)
        if row is None:
            return None
        return (row.settings or {}).get(SETTING_LAST_DAILY_REPORT)

    async def mark_daily_report(self, group_id: int, day_iso: str) -> None:
        await self._update_settings(group_id, {SETTING_LAST_DAILY_REPORT: day_iso})

    async def set_daily_report(self, group_id: int, enabled: bool) -> None:
        await self._update_settings(group_id, {SETTING_DAILY_REPORT: enabled})

    async def set_confirm_sensitive(self, group_id: int, enabled: bool) -> None:
        row = await self._settings_row(group_id)
        row.confirm_sensitive_actions = enabled
        await self._session.flush()

    async def set_warn_settings(
        self, group_id: int, *, warn_limit: int | None = None, warn_mute_seconds: int | None = None
    ) -> None:
        """تنظیمات اخطار را تغییر می‌دهد (مقادیر نامعتبر نادیده گرفته می‌شوند)."""
        changes: dict[str, int] = {}
        if warn_limit is not None:
            changes["warn_limit"] = _as_int(warn_limit, 3, 0, 50)
        if warn_mute_seconds is not None:
            changes["warn_mute_seconds"] = _as_int(warn_mute_seconds, 86400, 30, 366 * 86400)
        if changes:
            await self._update_settings(group_id, changes)

    async def _settings_row(self, group_id: int) -> GroupSettings:
        row = await self._session.get(GroupSettings, group_id)
        if row is None:
            row = GroupSettings(group_id=group_id, settings={})
            self._session.add(row)
            await self._session.flush()
        return row

    async def _update_settings(self, group_id: int, changes: dict[str, object]) -> None:
        row = await self._settings_row(group_id)
        # دیکشنری جدید می‌سازیم تا SQLAlchemy تغییر ستون JSON را تشخیص دهد.
        row.settings = {**(row.settings or {}), **changes}
        await self._session.flush()
