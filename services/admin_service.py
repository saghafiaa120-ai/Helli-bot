from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AuditAction, HelliRole
from core.permissions import derive_role
from core.timeutils import utcnow
from database.models import GroupAdmin
from database.repositories.admins import AdminRepository
from database.repositories.users import UserRepository
from domain.dto import AdminInfo
from services.audit_service import AuditService


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._admins = AdminRepository(session)
        self._users = UserRepository(session)
        self._audit = AuditService(session)

    async def sync_admins(self, group_id: int, admins: list[AdminInfo]) -> tuple[set[int], set[int]]:
        """فهرست مدیران گروه را با فهرست واقعی پلتفرم هم‌گام می‌کند.

        - مدیران جدید اضافه و نقش/دسترسی مدیران قبلی به‌روز می‌شود.
        - مدیری که دیگر مدیر پلتفرم نیست و نقش owner/admin داشته حذف می‌شود.
        - نقش‌هایی که دستی داخل حلی بات (مثلاً moderator) داده شده‌اند حفظ می‌شوند.
        - ربات‌ها ثبت نمی‌شوند.

        خروجی: (شناسه کاربران اضافه‌شده، شناسه کاربران حذف‌شده).
        """
        now = utcnow()
        existing = {row.user_id: row for row in await self._admins.list_for_group(group_id)}
        seen: set[int] = set()
        added: set[int] = set()

        for info in admins:
            if info.user.is_bot:
                continue
            user = await self._users.upsert(info.user)
            if user.id in seen:
                continue
            seen.add(user.id)
            role = derive_role(info.platform_role)
            row = existing.get(user.id)
            if row is None:
                self._session.add(
                    GroupAdmin(
                        group_id=group_id,
                        user_id=user.id,
                        platform_role=info.platform_role,
                        permissions=dict(info.permissions),
                        helli_role=role.value,
                        synced_at=now,
                    )
                )
                added.add(user.id)
            else:
                row.platform_role = info.platform_role
                row.permissions = dict(info.permissions)
                row.helli_role = role.value
                row.synced_at = now

        removed: set[int] = set()
        for user_id, row in existing.items():
            if user_id in seen:
                continue
            if row.helli_role in (HelliRole.OWNER.value, HelliRole.ADMIN.value):
                await self._session.delete(row)
                removed.add(user_id)
            else:
                row.platform_role = None
                row.permissions = None
                row.synced_at = now

        await self._session.flush()

        if added or removed:
            await self._audit.log(
                AuditAction.ADMINS_SYNCED,
                group_id=group_id,
                details={"added_user_ids": sorted(added), "removed_user_ids": sorted(removed)},
            )
        return added, removed

    async def get_role(self, group_id: int, user_id: int) -> HelliRole | None:
        """نقش داخلی کاربر در گروه؛ اگر مدیر نباشد None."""
        row = await self._admins.get(group_id, user_id)
        return HelliRole(row.helli_role) if row else None

    async def get_admin(self, group_id: int, user_id: int) -> GroupAdmin | None:
        """ردیف مدیریت کاربر (نقش پلتفرم و دسترسی‌ها)؛ برای بررسی مجوزها."""
        return await self._admins.get(group_id, user_id)

    async def list_group_ids_for_user(self, user_id: int) -> list[int]:
        """گروه‌هایی که کاربر در آن‌ها نقشی دارد (برای پنل کاربری)."""
        return await self._admins.list_group_ids_for_user(user_id)
