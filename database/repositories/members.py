from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import MemberStatus
from core.timeutils import utcnow
from database.models import GroupMember
from database.repositories._utils import get_or_create


class MemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, group_id: int, user_id: int) -> GroupMember | None:
        stmt = select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_status(
        self, group_id: int, user_id: int, status: str, *, seen_active: bool = False
    ) -> GroupMember:
        """وضعیت عضویت را ثبت می‌کند و زمان‌های ورود/خروج را متناسب با آن به‌روز می‌کند."""
        now = utcnow()
        is_member = status == MemberStatus.MEMBER.value
        member, created = await get_or_create(
            self.session,
            GroupMember,
            {"group_id": group_id, "user_id": user_id},
            {
                "status": status,
                "joined_at": now if is_member else None,
                "left_at": None if is_member else now,
                "last_active_at": now if (seen_active and is_member) else None,
            },
        )
        if created:
            return member

        if member.status != status:
            if is_member:
                member.joined_at = now
                member.left_at = None
            else:
                member.left_at = now
            member.status = status
        if seen_active and is_member:
            member.last_active_at = now
        await self.session.flush()
        return member
