from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import MemberStatus
from database.models import GroupMember
from database.repositories.members import MemberRepository


class MembershipService:
    def __init__(self, session: AsyncSession) -> None:
        self._members = MemberRepository(session)

    async def get(self, group_id: int, user_id: int) -> GroupMember | None:
        """وضعیت عضویت ثبت‌شده (اگر کاربر هرگز دیده نشده باشد None)."""
        return await self._members.get(group_id, user_id)

    async def set_status(self, group_id: int, user_id: int, status: str) -> GroupMember:
        """ثبت تغییر وضعیت عضویت (ورود، خروج، مسدودی) از رویدادهای پلتفرم."""
        return await self._members.set_status(group_id, user_id, status)

    async def touch_activity(self, group_id: int, user_id: int) -> GroupMember:
        """کاربری که پیام می‌دهد قطعاً عضو است؛ آخرین فعالیت او ثبت می‌شود."""
        return await self._members.set_status(
            group_id, user_id, MemberStatus.MEMBER.value, seen_active=True
        )
