from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import GroupAdmin


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_group(self, group_id: int) -> list[GroupAdmin]:
        stmt = select(GroupAdmin).where(GroupAdmin.group_id == group_id)
        return list((await self.session.execute(stmt)).scalars())

    async def get(self, group_id: int, user_id: int) -> GroupAdmin | None:
        stmt = select(GroupAdmin).where(
            GroupAdmin.group_id == group_id, GroupAdmin.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_group_ids_for_user(self, user_id: int) -> list[int]:
        """شناسه گروه‌هایی که کاربر در آن‌ها مدیر است."""
        stmt = select(GroupAdmin.group_id).where(GroupAdmin.user_id == user_id)
        return list((await self.session.execute(stmt)).scalars())
