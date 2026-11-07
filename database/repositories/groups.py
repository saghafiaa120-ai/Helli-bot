from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.timeutils import utcnow
from database.models import Group, GroupSettings
from database.repositories._utils import get_or_create
from domain.dto import ChatRef


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, platform: str, external_id: int) -> Group | None:
        stmt = select(Group).where(Group.platform == platform, Group.external_id == external_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, group_id: int) -> Group | None:
        return await self.session.get(Group, group_id)

    async def list_active(self, platform: str | None = None) -> list[Group]:
        """گروه‌هایی که ربات هنوز در آن‌هاست (برای گزارش شبانه و پنل)."""
        stmt = select(Group).where(Group.is_active.is_(True)).order_by(Group.id)
        if platform is not None:
            stmt = stmt.where(Group.platform == platform)
        return list((await self.session.execute(stmt)).scalars())

    async def list_by_ids(self, group_ids: list[int]) -> list[Group]:
        if not group_ids:
            return []
        stmt = select(Group).where(Group.id.in_(group_ids)).order_by(Group.id)
        return list((await self.session.execute(stmt)).scalars())

    async def get_or_create(self, chat: ChatRef) -> tuple[Group, bool]:
        """گروه را می‌گیرد یا می‌سازد. هنگام ساخت، ردیف تنظیمات پیش‌فرض هم ساخته می‌شود."""
        group, created = await get_or_create(
            self.session,
            Group,
            {"platform": chat.platform, "external_id": chat.external_id},
            {
                "title": chat.title,
                "username": chat.username,
                "is_active": True,
                "bot_is_admin": False,
                "added_at": utcnow(),
            },
        )
        if created:
            self.session.add(GroupSettings(group_id=group.id))
            await self.session.flush()
        return group, created

    @staticmethod
    def apply_chat_info(group: Group, chat: ChatRef) -> bool:
        """عنوان و نام کاربری گروه را به‌روز می‌کند؛ اگر تغییری بود True برمی‌گرداند."""
        changed = False
        if group.title != chat.title:
            group.title = chat.title
            changed = True
        if group.username != chat.username:
            group.username = chat.username
            changed = True
        return changed
